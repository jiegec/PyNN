import os
from numpy.testing import assert_array_equal
from pyNN.random import RandomDistribution
from pyNN.utility import init_logging
import quantities as pq
import numpy as np

try:
    import pyNN.neuron
    from pyNN.neuron.cells import _new_property, NativeCellType
    from nrnutils import Mechanism, Section, DISTAL
    have_neuron = True
except ImportError:
    have_neuron = False
import pytest


skip_ci = False
if "JENKINS_SKIP_TESTS" in os.environ:
    skip_ci = os.environ["JENKINS_SKIP_TESTS"] == "1"


def test_ticket168():
    """
    Error setting firing rate of `SpikeSourcePoisson` after `reset()` in NEURON
    http://neuralensemble.org/trac/PyNN/ticket/168
    """
    if not have_neuron:
        pytest.skip("neuron not available")
    pynn = pyNN.neuron
    pynn.setup()
    cell = pynn.Population(1, pynn.SpikeSourcePoisson(), label="cell")
    cell[0].rate = 12
    pynn.run(10.)
    pynn.reset()
    cell[0].rate = 12
    pynn.run(10.)
    assert pynn.get_current_time() == pytest.approx(10.0)  # places=11)
    assert cell[0]._cell.interval == 1000.0 / 12.0


class SimpleNeuron(object):

    def __init__(self, **parameters):
        # define ion channel parameters
        leak = Mechanism('pas', e=-65, g=parameters['g_leak'])
        hh = Mechanism('hh', gl=parameters['g_leak'], el=-65,
                       gnabar=parameters['gnabar'], gkbar=parameters['gkbar'])
        # create cable sections
        self.soma = Section(L=30, diam=30, mechanisms=[hh])
        self.apical = Section(L=600, diam=2, nseg=5, mechanisms=[leak], parent=self.soma,
                              connection_point=DISTAL)
        self.basilar = Section(L=600, diam=2, nseg=5, mechanisms=[leak], parent=self.soma)
        self.axon = Section(L=1000, diam=1, nseg=37, mechanisms=[hh])
        # synaptic input
        self.apical.add_synapse('ampa', 'Exp2Syn', e=0.0, tau1=0.1, tau2=5.0)

        # needed for PyNN
        self.source_section = self.soma
        self.source = self.soma(0.5)._ref_v
        self.parameter_names = ('g_leak', 'gnabar', 'gkbar')
        self.traces = {}
        self.recording_time = False

    def _set_g_leak(self, value):
        for sec in (self.apical, self.basilar):
            for seg in sec:
                seg.pas.g = value
        for sec in (self.soma, self.axon):
            for seg in sec:
                seg.hh.gl = value

    def _get_g_leak(self):
        return self.apical(0.5).pas.g
    g_leak = property(fget=_get_g_leak, fset=_set_g_leak)

    def _set_gnabar(self, value):
        for sec in (self.soma, self.axon):
            for seg in sec:
                seg.hh.gnabar = value

    def _get_gnabar(self):
        return self.soma(0.5).hh.gnabar
    gnabar = property(fget=_get_gnabar, fset=_set_gnabar)

    def _set_gkbar(self, value):
        for sec in (self.soma, self.axon):
            for seg in sec:
                seg.hh.gkbar = value

    def _get_gkbar(self):
        return self.soma(0.5).hh.gkbar
    gkbar = property(fget=_get_gkbar, fset=_set_gkbar)

    def memb_init(self):
        """needed for PyNN"""
        for sec in (self.soma, self.axon, self.apical, self.basilar):
            for seg in sec:
                seg.v = self.v_init


if have_neuron:
    class SimpleNeuronType(NativeCellType):
        default_parameters = {'g_leak': 0.0002, 'gkbar': 0.036, 'gnabar': 0.12}
        default_initial_values = {'v': -65.0}
        # this is not good - over-ride Population.can_record()?
        recordable = ['apical(1.0).v', 'soma(0.5).ina']
        units = {'apical(1.0).v': 'mV', 'soma(0.5).ina': 'mA/cm**2'}
        receptor_types = ['apical.ampa']
        model = SimpleNeuron


def test_electrical_synapse():
    pytest.skip("Skipping test for now as it produces a segmentation fault")
    if skip_ci:
        pytest.skip("Skipping test on CI server as it produces a segmentation fault")
    p1 = pyNN.neuron.Population(4, pyNN.neuron.standardmodels.cells.HH_cond_exp())
    p2 = pyNN.neuron.Population(4, pyNN.neuron.standardmodels.cells.HH_cond_exp())
    syn = pyNN.neuron.ElectricalSynapse(weight=1.0)
    C = pyNN.connectors.FromListConnector(np.array([[0, 0, 1.0],
                                                       [0, 1, 1.0],
                                                       [2, 2, 1.0],
                                                       [3, 2, 1.0]]),
                                          column_names=['weight'])
    prj = pyNN.neuron.Projection(p1, p2, C, syn,
                                 source='source_section.gap', receptor_type='source_section.gap')
    current_source = pyNN.neuron.StepCurrentSource(amplitudes=[1.0], times=[100])
    p1[0:1].inject(current_source)
    p2[2:3].inject(current_source)
    p1.record('v')
    p2.record('v')
    pyNN.neuron.run(200)
    p1_trace = p1.get_data(('v',)).segments[0].analogsignals[0]
    p2_trace = p2.get_data(('v',)).segments[0].analogsignals[0]
    # Check the local forward connection
    assert p2_trace[:, 0].max() - p2_trace[:, 0].min() > 50
    # Check the remote forward connection
    assert p2_trace[:, 1].max() - p2_trace[:, 1].min() > 50
    # Check the local backward connection
    assert p1_trace[:, 2].max() - p2_trace[:, 2].min() > 50
    # Check the remote backward connection
    assert p1_trace[:, 3].max() - p2_trace[:, 3].min() > 50


def test_record_native_model():
    if not have_neuron:
        pytest.skip("neuron not available")
    nrn = pyNN.neuron

    init_logging(logfile=None, debug=True)
    nrn.setup()

    parameters = {'g_leak': 0.0003}
    p1 = nrn.Population(10, SimpleNeuronType(**parameters))
    print(p1.get('g_leak'))
    p1.rset('gnabar', RandomDistribution('uniform', low=0.10, high=0.14))
    print(p1.get('gnabar'))
    p1.initialize(v=-63.0)

    current_source = nrn.StepCurrentSource(times=[50.0, 110.0, 150.0, 210.0],
                                           amplitudes=[0.4, 0.6, -0.2, 0.2])
    p1.inject(current_source)

    p2 = nrn.Population(1, nrn.SpikeSourcePoisson(rate=100.0))

    p1.record(['apical(1.0).v', 'soma(0.5).ina'])

    connector = nrn.AllToAllConnector()
    syn = nrn.StaticSynapse(weight=0.1)
    prj_alpha = nrn.Projection(p2, p1, connector, syn, receptor_type='apical.ampa')

    nrn.run(250.0)

    data = p1.get_data().segments[0].analogsignals
    assert len(data) == 2  # one array per variable
    names = set(sig.name for sig in data)
    assert names == set(('apical(1.0).v', 'soma(0.5).ina'))
    apical_v = [sig for sig in data if sig.name == 'apical(1.0).v'][0]
    soma_i = [sig for sig in data if sig.name == 'soma(0.5).ina'][0]
    assert apical_v.sampling_rate == 10.0 * pq.kHz
    assert apical_v.units == pq.mV
    assert soma_i.units == pq.mA / pq.cm**2
    assert apical_v.t_start == 0.0 * pq.ms
    # would prefer if it were 250.0, but this is a fundamental Neo issue
    assert apical_v.t_stop == 250.1 * pq.ms
    assert apical_v.shape == (2501, 10)
    return data


def test_tsodyks_markram_synapse():
    if not have_neuron:
        pytest.skip("neuron not available")
    sim = pyNN.neuron
    sim.setup()
    spike_source = sim.Population(1, sim.SpikeSourceArray(spike_times=np.arange(10, 100, 10)))
    neurons = sim.Population(5, sim.IF_cond_exp(
        e_rev_I=-75, tau_syn_I=np.arange(0.2, 0.7, 0.1)))
    synapse_type = sim.TsodyksMarkramSynapse(U=0.04, tau_rec=100.0,
                                             tau_facil=1000.0, weight=0.01,
                                             delay=0.5)
    connector = sim.AllToAllConnector()
    prj = sim.Projection(spike_source, neurons, connector,
                         receptor_type='inhibitory',
                         synapse_type=synapse_type)
    neurons.record('gsyn_inh')
    sim.run(100.0)
    tau_psc = np.array([c.weight_adjuster.tau_syn for c in prj.connections])
    assert_array_equal(tau_psc, np.arange(0.2, 0.7, 0.1))


def test_artificial_cells():
    if not have_neuron:
        pytest.skip("neuron not available")
    sim = pyNN.neuron
    sim.setup()
    input = sim.Population(1, sim.SpikeSourceArray(spike_times=np.arange(10, 100, 10)))
    p1 = sim.Population(3, sim.IntFire1(tau=10, refrac=2))
    p2 = sim.Population(3, sim.IntFire2())
    p3 = sim.Population(3, sim.IntFire4())
    projections = []
    for p in (p1, p2, p3):
        projections.append(
            sim.Projection(input, p, sim.AllToAllConnector(), sim.StaticSynapse(weight=0.1, delay=0.5),
                           receptor_type="default")
        )
        p.record('m')
    sim.run(100.0)
