#!/usr/bin/env python

import random
import sys
import time
from novaclient.v1_1 import client


def returnNovaObject(url, tenant, user, password):
    try:
        novaobject = client.Client(user, password, tenant, url)
        return novaobject
    except:
        assert None, "Unable to create nova client"


def get_image(image_name):
    for i in novaobject.images.list():
        if i.name == image_name:
            return i


def returnRandom(whatToRandomize, idonly=0, max_cores=8):
    def randomize(list):
        return list[(random.randint(0, len(list) - 1))]

    if whatToRandomize == "image":
        if idonly == 1:
            return randomize(novaobject.images.list()).id
        else:
            return randomize(novaobject.images.list())

    elif whatToRandomize == "instance":
        if idonly == 1:
            return randomize(novaobject.servers.list()).id
        else:
            return randomize(novaobject.servers.list())

    elif whatToRandomize == "flavor":
        flavas = [f for f in novaobject.flavors.list() if f.vcpus <= max_cores]
        if idonly == 1:
            return random.choice(flavas).id
        else:
            return random.choice(flavas)

    elif whatToRandomize == "floating_ip":
        if idonly == 1:
            return randomize(novaobject.floating_ips.list()).ip
        else:
            return randomize(novaobject.floating_ips.list())


def returnOpen(what_to_return, idonly=0):

    if what_to_return == "floating_ip":
        for floating_ip in novaobject.floating_ips.list():
            if floating_ip.instance_id == None and idonly == 1:
                return floating_ip.ip
            elif floating_ip.instance_id == None:
                return floating_ip

        try:
            quota_ips = int(novaobject.quotas.get(tenant).floating_ips)
            if (len(novaobject.floating_ips.list()) < quota_ips):
                if idonly == 1:
                    return novaobject.floating_ips.create().ip
                else:
                    return novaobject.floating_ips.create()

        except Exception as except_msg:
            error_msg = str(except_msg)
            if error_msg == "No more floating ips available. (HTTP 400)":
                return False
            elif error_msg == "Access was denied to this resource. (HTTP 403)":
                try:
                    floating_ip = novaobject.floating_ips.create().ip
                    return floating_ip
                except:
                    return False

        return False


def getServerObjectFromName(server_name):
    for server in novaobject.servers.list():
        if server.name == server_name:
            return server
    return False


def shutdownInstances():
    try:
        for server in novaobject.servers.list():
            if returnServerStatus(server) == "PAUSED":
                server.unpause()
            while returnServerStatus(server) != "ACTIVE":
                time.sleep(2)
            print "Deleting %s" % server.id
            server.delete()
            print "Deleted"
        return 1, "success"
    except Exception as except_msg:
        return 0, except_msg


def runServerThroughTests():

    def returnServerStatus(server):
        try:
            server.get()
            status = server.status
        except Exception as except_msg:
            if except_msg == 'This request was rate-limited. (HTTP 413)':
                print "Rate limited: Waiting 5 seconds"
                time.sleep(5)
                return returnServerStatus(server)
        else:
            return status

    def bootRandomInstance():
        try:
            randomName = "test-%d-%d" % (time.time(), random.randint(0, 99999))
            image = get_image('oneiric-server-cloudimg-amd64')
            assert image, "No image found"
            
            novaobject.servers.create(
                        image=image,
                        flavor=returnRandom('flavor', 1, max_cores=4),
                        name=randomName)
            print "Server %s" % randomName
            print "Started server"
            
            server = getServerObjectFromName(randomName)
            
            if server:
                while len(server.networks) == 0:
                    time.sleep(3)
                    server.get()
                floating_ip = returnOpen('floating_ip', 1)
                if floating_ip:
                    server.add_floating_ip(floating_ip)
                    print "Added floating ip %s" % floating_ip
            server.get()
            return True, server
        except Exception as except_msg:
            quota_exceeded = "InstanceLimitExceeded: Instance quota "
            quota_exceeded += "exceeded. You cannot run any "
            quota_exceeded += "more instances of this type. "
            quota_exceeded += "(HTTP 413)"
            if str(except_msg) == "This request was rate-limited. (HTTP 413)":
                assert None, "rate limited"
            elif str(except_msg) == quota_exceeded:
                assert None, "Quota exceeded"
            else:
                print str(except_msg)
            return False, except_msg

    def checkBooted(server):
        boot_time = 60
        booted = False
        boot_start = time.time()
        success_msg = 'cloud-init boot finished'

        while not booted and time.time() - boot_start < boot_time:
            console_output = novaobject.servers.get_console_output(server.id)
            if success_msg in console_output:
                booted = True
            time.sleep(3)
        print booted and "Boot successful" or "Boot failed"
        return booted, booted and '' or \
                    "Server not booted within %d sec" % (boot_time)

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
                if returnServerStatus(server) == expected_state:
                    action_done = True
                else:
                    time.sleep(3)
            print action_done and "%s successful" % action.capitalize()
            return action_done, action_done and '' or \
                    "Server not %s within %d sec" % (action, time_limit)
        except Exception as except_msg:
            return False, except_msg

    def resizeInstance(server):
        try:
            server.resize(returnRandom('flavor', 1))
            return True, "success"
        except Execrption as except_msg:
            return False, except_msg

    def destroyInstance(server):
        destroy_time = 60
        is_del = False
        start = time.time()

        server.delete()
        while not is_del and time.time() - start < destroy_time:
            if not any([s.id == server.id for s in novaobject.servers.list()]):
                is_del = True
                print "Server destroyed"
            else:
                time.sleep(1)
        return is_del, is_del and '' or \
                    "Server not destroyed within %d sec" % (destroy_time)

    perfect = 1

    start_worked, start_return = bootRandomInstance()

    if start_worked:
        server = start_return

        boot_worked, boot_return = checkBooted(server)
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

        destroy_worked, destroy_return = destroyInstance(start_return)
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
            runServerThroughTests()
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

    novaobject = returnNovaObject(auth_url, tenant, user, password)
    runServerThroughTests()
