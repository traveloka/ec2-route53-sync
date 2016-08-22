from setuptools import (
    find_packages,
    setup
)

setup(
    name='ec2-route53-sync',
    version='1.0.0.dev1',
    description='',
    url='https://github.com/traveloka/ec2-route53-sync/',
    # author='',
    license='MPLv2.0',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)'
    ],
    # keywords='',
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'boto3',
        'click>=6'
    ],
    entry_points={
        'console_scripts': [
            'ec2-route53-sync=route53_sync:sync_tag_with_zone'
        ]
    }
)
