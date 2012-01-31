#!/usr/bin/env python

import random
import sys
import time
from novaclient.v1_1 import client


def return_nova_object(url, tenant, user, password):
    try:
        nc = client.Client(user, password, tenant, url)
        return nc
    except:
        assert None, "Unable to create nova client"


def actions(action, expected_state, server, time_limit=60):
    action_done = False
    action_start = time.time()

    try:
        if action == "pause":
            server.pause()
        elif action == "unpause":
            server.unpause()
        elif action == "suspend":
            server.suspend()
        elif action == "resume":
            server.resume()

        while not action_done and time.time() - action_start < time_limit:
            if return_server_status(server) == expected_state:
                action_done = True
            else:
                time.sleep(3)

        action_msg = ""
        if not action_done:
            action_msg = "Server not %s within %d sec" % (action, time_limit)
        return action_done, action_msg

    except Exception as except_msg:
        return False, except_msg


def return_server_status(server):
    try:
        server.get()
        status = server.status
    except Exception as except_msg:
        if except_msg == 'This request was rate-limited. (HTTP 413)':
            print "Rate limited: Waiting 5 seconds"
            time.sleep(5)
            return return_server_status(server)
    else:
        return status


def get_image(image_name):
    for i in nc.images.list():
        if i.name == image_name:
            return i


def get_server_object_from_name(server_name):
    for server in nc.servers.list():
        if server.name == server_name:
            return server
    return False


def return_random(whatToRandomize, idonly=0, max_cores=8):
    def randomize(list):
        return list[(random.randint(0, len(list) - 1))]

    if whatToRandomize == "image":
        if idonly == 1:
            return randomize(nc.images.list()).id
        else:
            return randomize(nc.images.list())

    elif whatToRandomize == "instance":
        if idonly == 1:
            return randomize(nc.servers.list()).id
        else:
            return randomize(nc.servers.list())

    elif whatToRandomize == "flavor":
        flavas = [f for f in nc.flavors.list() if f.vcpus <= max_cores]
        if idonly == 1:
            return random.choice(flavas).id
        else:
            return random.choice(flavas)

    elif whatToRandomize == "floating_ip":
        if idonly == 1:
            return randomize(nc.floating_ips.list()).ip
        else:
            return randomize(nc.floating_ips.list())


def return_open(what_to_return, idonly=0):

    if what_to_return == "floating_ip":
        for floating_ip in nc.floating_ips.list():
            if floating_ip.instance_id == None and idonly == 1:
                return floating_ip.ip
            elif floating_ip.instance_id == None:
                return floating_ip

        try:
            quota_ips = int(nc.quotas.get(tenant).floating_ips)
            if (len(nc.floating_ips.list()) < quota_ips):
                if idonly == 1:
                    return nc.floating_ips.create().ip
                else:
                    return nc.floating_ips.create()

        except Exception as except_msg:
            error_msg = str(except_msg)
            if error_msg == "No more floating ips available. (HTTP 400)":
                return False
            elif error_msg == "Access was denied to this resource. (HTTP 403)":
                try:
                    floating_ip = nc.floating_ips.create().ip
                    return floating_ip
                except:
                    return False

        return False


def destroy_instance(server):
    destroy_time = 60
    is_del = False
    destroy_start = time.time()

    server_status = return_server_status(server)
    is_active = return_server_status == "ACTIVE"

    start = time.time()
    if server_status in ["SUSPENDED", "PAUSED"]:
        if server_status == "SUSPENDED":
            actions('resume', 'ACTIVE', server)
        else:
            actions('unpause', 'ACTIVE', server)

    server.delete()
    while not is_del and time.time() - destroy_start < destroy_time:
        if not any([s.id == server.id for s in nc.servers.list()]):
            is_del = True
        else:
            time.sleep(1)
    return is_del, is_del and '' or \
                "Server not destroyed within %d sec" % (destroy_time)


def shutdown_instances(server=None):
    try:
        if not server:
            for server in nc.servers.list():
                destroy_instance(server)
            return 1, "success"
        else:
            destroy_instance(server)
            return 1, "success"

    except Exception as except_msg:
        return 0, except_msg


def run_server_through_tests(number_of_runs=1, destroy_instances=False):

    def boot_random_instance():
        try:
            random_name = "test-%d-%d" % (time.time(), random.randint(0, 999))
            image = get_image('oneiric-server-cloudimg-amd64')
            assert image, "No image found"

            nc.servers.create(
                        image=image,
                        flavor=return_random('flavor', 1, max_cores=4),
                        name=random_name)
            print "Server %s" % random_name

            server = get_server_object_from_name(random_name)
            if server:
                while return_server_status(server) != "ACTIVE":
                    time.sleep(1)
                while len(server.networks) == 0:
                    time.sleep(3)
                    server.get()
                floating_ip = return_open('floating_ip', 1)
                if floating_ip:
                    server.add_floating_ip(floating_ip)

            else:
                return False

            return True, server

        except Exception as except_msg:
            quota_exceeded = "InstanceLimitExceeded: Instance quota "
            quota_exceeded += "exceeded. You cannot run any "
            quota_exceeded += "more instances of this type. "
            quota_exceeded += "(HTTP 413)"
            if str(except_msg) == "This request was rate-limited. (HTTP 413)":
                print "rate limited"
                time.sleep(10)
                return boot_random_instance()
            elif str(except_msg) == quota_exceeded:
                print "Quota exceeded, removing instances"
                for server in nc.servers.list():
                    destroy_instance(server)
                return boot_random_instance()
            else:
                print str(except_msg)
            return False, except_msg

    def check_booted(server):
        boot_time = 60
        booted = False
        boot_start = time.time()
        success_msg = 'cloud-init boot finished'

        try:
            while not booted and time.time() - boot_start < boot_time:
                console_output = nc.servers.get_console_output(server.id)
                if success_msg in console_output:
                    booted = True
                time.sleep(3)
            if not booted:
                print "Boot failed"
            return booted, booted and '' or \
                        "Server not booted within %d sec" % (boot_time)
        except Exception as exception:
            print "Exception in get_console_output"
            print exception
            return false, exception

    def resize_instance(server):
        try:
            server.resize(return_random('flavor', 1, max_cores=4))
            return True, "success"
        except Execrption as except_msg:
            return False, except_msg

    def create_image(server):
        try:
            image_created = False
            start = time.time()
            create_time = 60
            server.create_image('%s_image' % server.name)

            while not image_created and time.time() - start < create_time:
                for i in nc.images.list():
                    if i.name == image_name:
                        image_created = True
                if not image_created:
                    time.sleep(3)
            if image_created:
                return True, "success"
            else:
                return False, "Image not created in %s sec" % create_time
        except Execrption as except_msg:
            return False, except_msg

    perfect = 1

    for x in range(number_of_runs):

        start_worked, start_return = boot_random_instance()

        if start_worked:
            server = start_return

            boot_worked, boot_return = check_booted(server)

            if not boot_worked:
                print 'Server boot failed: %s' % boot_return
                perfect = 0

            pause_worked, pause_return = actions('pause', 'PAUSED', server)
            if not pause_worked:
                print 'Server pause failed: %s' % pause_return
                perfect = 0

            unpause_worked, unpause_return = actions('unpause', 'ACTIVE', server)
            if not unpause_worked:
                print 'Server unpause failed: %s' % unpause_return
                perfect = 0

            sus_worked, sus_return = actions('suspend', 'SUSPENDED', server)
            if not sus_worked:
                print 'Server suspend failed: %s' % sus_return
                perfect = 0

            if sus_worked:
                resume_worked, resume_return = actions('resume', 'ACTIVE', server)
                if not resume_worked:
                    print 'Server resume failed: %s' % resume_return
                    perfect = 0

            if destroy_instances:
                destroy_worked, destroy_return = destroy_instance(start_return)
                if not destroy_worked:
                    print 'Server destroy failed: %s' % destroy_return
                    perfect = 0

        else:
            print 'Server start failed: %s' % start_return
            perfect = 0

    if perfect == 0:
        if start_return == "This request was rate-limited. (HTTP 413)":
            print "Rate limited, sleeping for 10 seconds then will try again"
            time.sleep(10)
            run_server_through_tests()
        else:
            return False, "Something went wrong with something"

    else:
        return True, "Seems to have ran through all operations smoothly"


if __name__ == '__main__':
    try:
        import config
    except:
        print "unable to import defaults"

    if len(sys.argv) >= 2:
        tenant = sys.argv[1]
    else:
        tenant = 'ben'

    if len(sys.argv) >= 3:
        user = sys.argv[2]
    else:
        user = tenant

    if len(sys.argv) >= 4:
        password = sys.argv[3]
    else:
        password = config.users[user]
        password = 'pa55w0rd'

    if len(sys.argv) >= 5:
        auth_url = "http://%s:5000/v2.0/" % sys.argv[4]
    else:
        auth_url = "http://%s:5000/v2.0/" % config.master

    nc = return_nova_object(auth_url, tenant, user, password)

    if len(sys.argv) >= 6:
        run_server_through_tests(number_of_runs=int(sys.argv[5]))
    else:
        run_server_through_tests()
