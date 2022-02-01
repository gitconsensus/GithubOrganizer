# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open

version = '0.1.0'

try:
    long_description = open('README.md').read()
except:
    long_description = ''


setup(

  name = 'githuborganizer',

  version = version,
  packages=find_packages(),

  description = '',
  long_description=long_description,
  long_description_content_type='text/markdown',
  python_requires='>=3',

  author = 'Robert Hafner',
  author_email = 'tedivm@tedivm.com',
  url = 'https://github.com/tedivm/githuborganizer',
  download_url = "https://github.com/tedivm/githuborganizer/archive/v%s.tar.gz" % (version),
  keywords = 'automation github organizations',

  classifiers = [
    'Development Status :: 4 - Beta',
    'License :: OSI Approved :: MIT License',

    'Intended Audience :: Developers',
    'Topic :: Software Development :: Version Control',

    'Programming Language :: Python :: 3',
  ],

  install_requires=[
    'Beaker>=1.11.0,<2',
    'celery>=5.2.3,<6',
    'click>=8.0.3,<9.0',
    'cryptography>=36.0.1<37.0',
    'github3.py>=3.0.0,<4',
    'github3apps.py>=0.2.2,<0.3',
    'pyjwt>=2.3.0,<3',
    'PyYAML>=6.0,<7',
    'fastapi>=0.73.0',
  ],

  extras_require={
    'dev': [
      'pypandoc',
      'twine',
      'wheel'
    ],
  },
)
