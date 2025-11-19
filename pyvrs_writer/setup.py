# pyvrs_writer/setup.py
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import sys
import os
from pathlib import Path

class CMakeBuild(build_ext):
    def run(self):
        # CMakeを使用してビルド
        import subprocess

        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)

        # CMake configure
        subprocess.check_call([
            'cmake',
            str(Path(__file__).parent.absolute()),
            f'-DCMAKE_BUILD_TYPE=Release',
        ], cwd=build_temp)

        # CMake build
        subprocess.check_call([
            'cmake',
            '--build', '.',
            '--config', 'Release',
            '--', '-j4'
        ], cwd=build_temp)

        # .soファイルをコピー
        import shutil
        so_file = list(build_temp.glob('_pyvrs_writer*.so'))[0]
        dest = Path(self.build_lib) / 'pyvrs_writer'
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(so_file, dest)

setup(
    name='pyvrs_writer',
    version='0.1.0',
    author='Your Name',
    description='Python bindings for VRS file writing',
    long_description='',
    packages=['pyvrs_writer'],
    package_dir={'': 'python'},
    ext_modules=[Extension('_pyvrs_writer', [])],
    cmdclass={'build_ext': CMakeBuild},
    zip_safe=False,
    python_requires='>=3.9',
)
