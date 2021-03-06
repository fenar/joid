#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This script generates a juju deployer bundle based on
scenario name, and lab config file.

Parameters:
 -s, --scenario : scenario name
 -l, --lab      : lab config file
"""

from optparse import OptionParser
from jinja2 import Environment, FileSystemLoader
from distutils.version import LooseVersion, StrictVersion
import os
import subprocess
import random
import yaml
import sys

#
# Parse parameters
#

parser = OptionParser()
parser.add_option("-s", "--scenario", dest="scenario", help="scenario name")
parser.add_option("-l", "--lab", dest="lab", help="lab config file")
(options, args) = parser.parse_args()
scenario = options.scenario
labconfig_file = options.lab

#
# Set Path and configs path
#

scenarioconfig_file = 'default_deployment_config.yaml'
# Capture our current directory
jujuver = subprocess.check_output(["juju", "--version"])

TPL_DIR = os.path.dirname(os.path.abspath(__file__))+'/config_tpl/juju2/bundlek8_tpl'

#
# Prepare variables
#

# Prepare a storage for passwords
passwords_store = dict()

#
# Local Functions
#


def load_yaml(filepath):
    """Load YAML file"""
    with open(filepath, 'r') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

#
# Templates functions
#


def unit_qty():
    """Return quantity of units to deploy"""
    global config
    if config['os']['ha']['mode'] == 'ha':
        return config['os']['ha']['cluster_size']
    else:
        return 1


def unit_ceph_qty():
    """Return size of the ceph cluster"""
    global config
    if config['os']['ha']['mode'] == 'ha':
        return config['os']['ha']['cluster_size']
    else:
        if config['opnfv']['units'] >= 3:
            return config['os']['ha']['cluster_size']
        else:
            return 2

def unit_scaleio_qty():
    """Return size of the scaleio cluster"""
    return 3

def to_select(qty=False):
    """Return a random list of machines numbers to deploy"""
    global config
    if not qty:
        qty = config['os']['ha']['cluster_size'] if \
                config['os']['ha']['mode'] == 'ha' else 1
    if config['os']['hyperconverged']:
        return random.sample(range(0, config['opnfv']['units']), qty)
    else:
        return random.sample(range(0, qty), qty)


def get_password(key, length=16, special=False):
    """Return a new random password or a already created one"""
    global passwords_store
    if key not in passwords_store.keys():
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        upperalphabet = alphabet.upper()
        char_list = alphabet + upperalphabet + '0123456789'
        pwlist = []
        if special:
            char_list += "+-,;./:?!*"
        for i in range(length):
            pwlist.append(char_list[random.randrange(len(char_list))])
        random.shuffle(pwlist)
        passwords_store[key] = "".join(pwlist)
    return passwords_store[key]

#
# Config import
#

# Load scenario Config
config = load_yaml(scenarioconfig_file)
# Load lab Config
config.update(load_yaml(labconfig_file))

# We transform array to hash for an easier work
config['opnfv']['spaces_dict'] = dict()
for space in config['opnfv']['spaces']:
    config['opnfv']['spaces_dict'][space['type']] = space
config['opnfv']['storage_dict'] = dict()
for storage in config['opnfv']['storage']:
    config['opnfv']['storage_dict'][storage['type']] = storage

#
# Parse scenario name
#

# Set default scenario name
if not scenario:
    scenario = "k8-nosdn-baremetal-core"

# Parse scenario name
try:
    sc = scenario.split('-')
    (sdn, features, hamode) = sc[1:4]
    features = features.split('_')
    if len(sc) > 4:
        extra = sc[4].split('_')
    else:
        extra = []
except ValueError as err:
    print('Error: Bad scenario name syntax, use '
          '"k8-nosdn-baremetal-core" format')
    sys.exit(1)

#
# Update config with scenario name
#

if 'dpdk' in features:
    config['os']['network']['dpdk'] = True
if 'lb' in features:
    config['k8']['feature']['loadbalancer'] = True

# change ha mode
config['k8']['network']['controller'] = sdn

# Set beta option from extra
if 'hugepages' in extra:
    config['os']['beta']['huge_pages'] = True
if 'lb' in extra:
    config['k8']['feature']['loadbalancer'] = True
if 'mitaka' in extra:
    config['os']['release'] = 'mitaka'
if 'xenial' in extra:
    config['ubuntu']['release'] = 'xenial'

#
# Transform template to bundle.yaml according to config
#

# Create the jinja2 environment.
env = Environment(loader=FileSystemLoader(TPL_DIR),
                  trim_blocks=True)
template = env.get_template('bundle.yaml')

# Add functions
env.globals.update(get_password=get_password)
env.globals.update(unit_qty=unit_qty)
env.globals.update(unit_ceph_qty=unit_ceph_qty)
env.globals.update(unit_scaleio_qty=unit_scaleio_qty)
env.globals.update(to_select=to_select)

# Render the template
output = template.render(**config)

# Check output syntax
try:
    yaml.load(output)
except yaml.YAMLError as exc:
    print(exc)

# print output
print(output)
