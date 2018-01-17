#!/usr/bin/env python
import os
import io
import re
from setuptools import setup


def read(*path):
    return io.open(
        os.path.join(*([os.path.dirname(__file__)] + list(path))),
        encoding="UTF8"
    ).read()


VERSION = re.compile(r".*__version__ = '(.*?)'", re.S)\
    .match(read('ipmt', '__init__.py')).group(1)

readme = read('README.rst')

requirements = read('requirements.txt')

test_requirements = read('requirements_dev.txt').replace('-r requirements.txt', requirements)

setup(
    name='ipmt',
    version=VERSION,
    description="Schema migration tools for PostgreSQL",
    long_description=readme,
    author="InPlat",
    author_email='dev@inplat.ru',
    url='https://github.com/inplat/ipmt',
    packages=[
        'ipmt',
    ],
    package_dir={'ipmt': 'ipmt'},
    entry_points={
        'console_scripts': [
            'ipmt=ipmt.cli:main'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    zip_safe=False,
    keywords='ipmt',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
