from setuptools import setup, find_packages

version = '0.17'

setup(name='chut',
      version=version,
      description="Small tool to interact with shell and pipes",
      long_description=open('README.rst').read(),
      classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: POSIX',
          'Programming Language :: Unix Shell',
          'Programming Language :: Python :: 3',
      ],
      keywords='sh shell bash',
      author='Gael Pasgrimaud',
      author_email='gael@gawel.org',
      url='https://github.com/gawel/chut/',
      license='MIT',
      packages=find_packages(exclude=['docs', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=['six', 'pathlib', 'docopt', 'ConfigObject'],
      entry_points="""
      [console_scripts]
      chutify = chut.scripts:chutify
      [zc.buildout]
      default = chut.recipe:Recipe
      """,
      )
