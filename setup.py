#!/usr/bin/env python

try:
    from setuptools import setup
    from setuptools.command.build_py import build_py as _build
    tests_req = ["mpi4py", "scipy", "matplotlib", "Cheetah3", "h5py"]
except ImportError:
    from distutils.core import setup
    from distutils.command.build_py import build_py as _build

import os
import subprocess


def run_command(path, working_directory):
    p = subprocess.Popen(path, shell=True, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True,
                         cwd=working_directory)
    stdout, stderr = p.communicate()
    return p.returncode, stdout.split("\n")


class build(_build):
    """At the end of the build process, try to compile NEURON and NEST extensions."""

    def run(self):
        self.distribution.convert_2to3_doctests = []  # workaround for bug
        # see https://app.travis-ci.com/github/NeuralEnsemble/PyNN/jobs/582235672
        _build.run(self)
        # try to compile NEURON extensions
        nrnivmodl = self.find("nrnivmodl")

        if nrnivmodl:
            print("nrnivmodl found at", nrnivmodl)
            result, stdout = run_command(nrnivmodl,
                                         os.path.join(os.getcwd(), self.build_lib, 'pyNN/neuron/nmodl'))
            # test if nrnivmodl was successful
            if result != 0:
                print("Unable to compile NEURON extensions. Output was:")
                print('  '.join([''] + stdout))  # indent error msg for easy comprehension
            else:
                print("Successfully compiled NEURON extensions.")
        else:
            print("Unable to find nrnivmodl. It will not be possible to use the pyNN.neuron module.")
        # try to compile NEST extensions
        nest_config = self.find("nest-config")
        if nest_config:
            print("nest-config found at", nest_config)
            nest_build_dir = os.path.join(os.getcwd(), self.build_lib, 'pyNN/nest/_build')
            if not os.path.exists(nest_build_dir):
                os.mkdir(nest_build_dir)
            result, stdout = run_command("cmake -Dwith-nest={} ../extensions".format(nest_config),
                                         nest_build_dir)
            if result != 0:
                print("Problem running cmake. Output was:")
                print('  '.join([''] + stdout))
            else:
                result, stdout = run_command("make", nest_build_dir)
                if result != 0:
                    print("Unable to compile NEST extensions. Output was:")
                    print('  '.join([''] + stdout))
                else:
                    # should really move this to install stage
                    result, stdout = run_command("make install", nest_build_dir)
                    if result != 0:
                        print("Unable to install NEST extensions. Output was:")
                        print('  '.join([''] + stdout))
                    else:
                        print("Successfully compiled NEST extensions.")

    def find(self, command):
        """Try to find an executable file."""
        path = os.environ.get("PATH", "").split(os.pathsep)
        cmd = ''
        for dir_name in path:
            abs_name = os.path.abspath(os.path.normpath(os.path.join(dir_name, command)))
            if os.path.isfile(abs_name):
                cmd = abs_name
                break
        return cmd


setup(
    name="PyNN",
    version="0.10.2.dev",
    packages=['pyNN', 'pyNN.nest', 'pyNN.neuron',
              'pyNN.brian2', 'pyNN.common', 'pyNN.mock', 'pyNN.neuroml',
              'pyNN.recording', 'pyNN.standardmodels', 'pyNN.descriptions',
              'pyNN.nest.standardmodels', 'pyNN.neuroml.standardmodels',
              'pyNN.neuron.standardmodels',
              'pyNN.brian2.standardmodels', 'pyNN.utility', 'pyNN.nineml',
              'pyNN.serialization'],
    package_data={'pyNN': ['neuron/nmodl/*.mod',
                           'nest/extensions/*.h',
                           'nest/extensions/*.cpp',
                           'nest/extensions/CMakeLists.txt',
                           'nest/extensions/sli/*.sli',
                           "descriptions/templates/*/*"]},
    author="The PyNN team",
    author_email="andrew.davison@unic.cnrs-gif.fr",
    description="A Python package for simulator-independent specification of neuronal network models",
    long_description=open("README.rst").read(),
    license="CeCILL http://www.cecill.info",
    keywords="computational neuroscience simulation neuron nest brian2 neuromorphic",
    url="http://neuralensemble.org/PyNN/",
    classifiers=['Development Status :: 4 - Beta',
                 'Environment :: Console',
                 'Intended Audience :: Science/Research',
                 'License :: Other/Proprietary License',
                 'Natural Language :: English',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.7',
                 'Programming Language :: Python :: 3.8',
                 'Programming Language :: Python :: 3.9',
                 'Topic :: Scientific/Engineering'],
    cmdclass={'build_py': build},
    install_requires=['numpy>=1.18.5', 'lazyarray>=0.5.2', 'neo>=0.11.0',
                      'quantities>=0.12.1'],
    extras_require={
        'examples': ['matplotlib', 'scipy'],
        'plotting': ['matplotlib', 'scipy'],
        'MPI': ['mpi4py'],
        'sonata': ['h5py']
    },
    tests_require=tests_req
)
