# ec2-route53-sync
Syncs EC2 instances' Route53 DNS entries

## Overview

[![Build Status](https://travis-ci.org/traveloka/ec2-route53-sync.svg?branch=master)](https://travis-ci.org/traveloka/ec2-route53-sync)
[![Coverage Status](https://coveralls.io/repos/github/traveloka/ec2-route53-sync/badge.svg?branch=master)](https://coveralls.io/github/traveloka/ec2-route53-sync?branch=master)

## Installation

    pip install git+https://github.com/traveloka/ec2-route53-sync.git

## Usage

For users:

    ec2-route53-sync --help

## For developers

    git clone git@github.com:traveloka/ec2-route53-sync.git
    pip install -r dev-requirements.txt
    python -m ec2_route53_sync --help

To test the wrapper script:

    pip install --editable .
    rehash # only for CSH and ZSH users
    ec2-route-53-sync --help
