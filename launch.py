#!/usr/bin/env python

import os
import paramiko
import random
import sys
import time
from novaclient.v1_1 import client

floating_ips_max_check = 10
nc = False


def check_sec_group():
    """see if port 22 is opened in securitry group for ping cmd over ssh"""

    try:
        sec_group_name = "default"
        sec_group_object = False
        has_port = False

        for sec_group in nc.security_groups.list():
            if sec_group.name == sec_group_name:
                sec_group_object = sec_group

        for rule in sec_group.rules:
            if rule['from_port'] == 22:
                has_port = True

        if not has_port:
            nc.security_group_rules.create(sec_group_object.id,
                                                'tcp', 22, 22, '0.0.0.0/0')

    except Exception as ex:
        print ex
        return False, ex
    return True, sec_group_object


def get_key():
    """create ssh keys to connect to server"""

    key_name = "key-%d-%d" % (time.time(), random.randint(0, 99999999))
    dummy = os.popen('ssh-keygen -t rsa -P "" -f %s' % key_name).readlines()
    public_key = open('%s.pub' % key_name, 'r').readlines()[0]
    created_key = nc.keypairs.create(key_name.split('/')[-1], public_key)
    return created_key, key_name


def assign_floating_ip(server_name):
    """assign or create a floating ip for instance wrapper"""

    server = False
    for s in nc.servers.list():
        if s.name == server_name:
            server = s

    if server:
        ip = get_floating_ip()
        if ip:
            server.add_floating_ip(ip)
            return ip

    return False


def get_floating_ip():
    """assign or create a floating ip for instance"""

    dont_use = ['50.56.12.240', '50.56.12.241', '50.56.12.242', '50.56.12.243']
    for floating_ip in nc.floating_ips.list():
        if floating_ip.instance_id == None and floating_ip.ip not in dont_use:
            return floating_ip.ip

    try:
        for x in range(floating_ips_max_check):
            floating_ip = nc.floating_ips.create()
            if floating_ip.ip not in dont_use:
                return floating_ip.ip
    except:
        return False

    return False


def connect_to_server(ssh_connect_info, port=22):
    """return ssh connection"""

    server_ip = ssh_connect_info['ip']
    login_name = ssh_connect_info['login']
    key_location = ssh_connect_info['key']
    connection_good = False

    x = 0
    while not connection_good:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(server_ip, username=login_name,
                                key_filename=key_location)
            return ssh, "SSH connection active"
        except Exception as ex:
            if x < 10:
                time.sleep(2)
            else:
                return False, "Could not complete ssh connection"

    return False, "Shouldn't get here"


def ping_thing(ssh_connection_dict):
    """do some pingin"""

    check_sec_group()
    pingers = ['4.2.2.1', 'www.google.com']
    ping_good = True
    for pingee in pingers:
        ssh, return_str = connect_to_server(ssh_connection_dict)
        if ssh:
            stdin, stdout, stderr = ssh.exec_command('ping -w 3 %s' % pingee)
            channel = stdout.channel
            status = channel.recv_exit_status()
            ping_return = stdout.readlines()
            for line in ping_return:
                if "transmitted" in line:
                    transmitted = line.split(',')[0].lstrip().split(' ')[0]
                    received = line.split(',')[1].lstrip().split(' ')[0]
                    packet_loss = line.split(',')[2].lstrip().split(' ')[0]
                    print "Ping Results %s: %s/%s %s loss" % (pingee,
                                received, transmitted, packet_loss)
                    if packet_loss == "100%":
                        ping_good = False
            ssh.close()
            channel.close()
    return ping_good


def launch(auth_url, tenant, user, password, destroy_time=60, boot_time=60):
    """launch and terminate a VM within a specified time"""

    global nc
    nc = client.Client(user, password, tenant, auth_url)
    name = "test-%d-%d" % (time.time(), random.randint(0, 99999999))

    def get_image(image_name):
        for i in nc.images.list():
            if i.name == image_name:
                return i

    def get_flavor(max_cores):
        flavors = [f for f in nc.flavors.list() if f.vcpus <= max_cores]
        return random.choice(flavors)

    image = get_image('oneiric-server-cloudimg-amd64')
    assert image, "No image found"
    print image

    flavor = get_flavor(4)
    assert flavor, "No satisfying flavor"
    print flavor

    nova_key, local_key = get_key()
    assert nova_key, "Error with key"

    new_server = nc.servers.create(image=image,
                                   flavor=flavor,
                                   name=name,
                                   key_name=nova_key.name)
    print new_server

    server_id = new_server.id

    while nc.servers.get(server_id).status != 'ACTIVE':
        time.sleep(2)

    booted = False
    boot_start = time.time()
    success_msg = 'cloud-init boot finished'

    while not booted and time.time() - boot_start < boot_time:
        console_output = nc.servers.get_console_output(server_id)
        if success_msg in console_output:
            booted = True
        else:
            time.sleep(3)

    ping_worked = False
    floating_ip = assign_floating_ip(name)
    if floating_ip:
        ssh_connect_info = {'ip': floating_ip, 'login': 'ubuntu',
                                        'key': local_key}
        ping_worked = ping_thing(ssh_connect_info)

    nc.servers.delete(server_id)
    is_del = False
    start = time.time()

    while not is_del and time.time() - start < destroy_time:
        if not any([s.id == server_id for s in nc.servers.list()]):
            is_del = True
        else:
            time.sleep(1)

    #clean up.  remove keys local and for nova
    os.system('rm %s*' % local_key)
    nova_key.delete()

    if not booted and not is_del:
        print "Server %s not booted within %d sec" % (name, boot_time)
    assert is_del, "Server %s not deleted within %d sec" % (name, destroy_time)
    assert booted, "Server %s not booted within %d sec" % (name, boot_time)
    assert floating_ip, "Could not get floating ip"
    assert ping_worked, "Pinging test had 100% loss on one of the pingees"

if __name__ == '__main__':
    try:
        import config
    except:
        print "unable to import defaults"

    if len(sys.argv) >= 2:
        tenant = sys.argv[1]
    else:
        tenant = 'admin'

    if len(sys.argv) >= 3:
        user = sys.argv[2]
    else:
        user = tenant

    if len(sys.argv) >= 4:
        password = sys.argv[3]
    else:
        password = config.users[user]

    if len(sys.argv) >= 5:
        auth_url = "http://%s:5000/v2.0/" % sys.argv[4]
    else:
        auth_url = "http://%s:5000/v2.0/" % config.master

    launch(auth_url, tenant, user, password)
    print "success"
