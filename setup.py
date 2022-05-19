from setuptools import setup

setup(
   name='friktionless',
   version='0.0.1',
   description='A utility library for the friktion team to automate data analysis and infrastructure',
   author='Matt Martin',
   author_email='matt@friktionlabs.com',
   packages=['friktionless'], 
   install_requires=['altair','pandas','google-cloud-storage']
)