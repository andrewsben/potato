#!/usr/bin/python

import ConfigParser
import novaclient
import random
import sys
import time
from novaclient.v1_1 import client


def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1


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


def returnRandom(whatToRandomize, idonly=0):
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
        if idonly == 1:
            return randomize(novaobject.flavors.list()).id
        else:
            return randomize(novaobject.flavors.list())

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
            quota_ips = int(novaobject.quotas.get(
                               novaconfig['os_auth_tenant']).floating_ips)
            if (len(novaobject.floating_ips.list()) < quota_ips):
                if idonly == 1:
                    print "creating ip"
                    return novaobject.floating_ips.create().ip
                    print "past creating ip"
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


def startServer():
    def bootRandomInstance():
        try:
            randomName = "test-%d-%d" % (time.time(), random.randint(0, 99999))
            novaobject.servers.create(
                        image=returnRandom('image', 1),
                        flavor=returnRandom('flavor', 1),
                        name=randomName)
            print "Booted server %s" % randomName
            server = getServerObjectFromName(randomName)
            if server:
                while len(server.networks) == 0:
                    time.sleep(3)
                    server.get()
                floating_ip = returnOpen('floating_ip', 1)
                if floating_ip:
                    server.add_floating_ip(floating_ip)
                    print "Added floating ip"
            server.get()
            return True, server
        except Exception as except_msg:
            quota_exceeded = "InstanceLimitExceeded: Instance quota "
            quota_exceeded += "exceeded. You cannot run any "
            quota_exceeded += "more instances of this type. "
            quota_exceeded += "(HTTP 413)"
            if str(except_msg) == "This request was rate-limited. (HTTP 413)":
                print "rate limited, sleeping now"
                time.sleep(10)
            elif str(except_msg) == quota_exceeded:
                shutdownInstances()
            else:
                print str(except_msg)
            return False, except_msg

    def pauseInstance(server):
        try:
            server.pause()
            while returnServerStatus(server) == 'ACTIVE':
                time.sleep(2)
            print "Paused"
            return True, "success"
        except Exception as except_msg:
            return False, except_msg

    def unpauseInstance(server):
        try:
            server.unpause()
            while returnServerStatus(server) != 'ACTIVE':
                time.sleep(2)
            print "Unpaused"
            return True, "success"
        except Exception as except_msg:
            return False, except_msg

    def suspendInstance(server):
        try:
            server.suspend()
            while returnServerStatus(server) != 'SUSPENDED':
                time.sleep(2)
            print "Suspended"
            return True, "success"
        except Exception as except_msg:
            return False, except_msg

    def resumeInstance(server):
        try:
            server.resume()
            while returnServerStatus(server) != 'ACTIVE':
                time.sleep(2)
            print "Resumed"
            return True, "success"
        except Exception as except_msg:
            return False, except_msg

    def resizeInstance(server):
        try:
            server.resize(returnRandom('flavor', 1))
            return True, "success"
        except Execrption as except_msg:
            return False, except_msg

    perfect = 1
    start_worked, start_return = bootRandomInstance()
    if start_worked:
        if not start_worked:
            print start_return
            perfect = 0
        pause_worked, pause_return = pauseInstance(start_return)
        if not pause_worked:
            print pause_return
            perfect = 0
        unpause_worked, unpause_return = unpauseInstance(start_return)
        if not unpause_worked:
            print unpause_return
            perfect = 0
        suspend_worked, suspend_return = suspendInstance(start_return)
        if not suspend_worked:
            print suspend_return
            perfect = 0
        resume_worked, resume_return = resumeInstance(start_return)
        if not resume_worked:
            print resume_return
            perfect = 0
    else:
        print start_return
        perfect = 0
        if start_return == "This request was rate-limited. (HTTP 413)":
            print "Rate limited, sleeping for 10 seconds"
            time.sleep(10)
    if perfect == 0:
        return False, "Something went wrong with something"
    else:
        return True, "Seems to have ran through all operations smoothly"


delete_servers = False
config_name = "Ben"

if len(sys.argv) >= 2:
    config_name = sys.argv[1]
    while config_name not in ['Admin', 'Ben', 'Delete']:
        print "Admin or Ben are the options"
        config_name = raw_input().strip()
    if config_name == 'Delete':
        delete_servers = True
        config_name = "Ben"

if len(sys.argv) >= 3:
    try:
        number_of_runs = int(sys.argv[2])
    except:
        number_of_runs = 10
else:
    number_of_runs = 10

Config = ConfigParser.ConfigParser()
Config.read('config.ini')
novaconfig = ConfigSectionMap(config_name)
novaobject = client.Client(novaconfig['nova_username'],
                                        novaconfig['nova_password'],
                                        novaconfig['nova_project_id'],
                                        novaconfig['nova_url'])

if delete_servers:
    shutdownInstances()
    print "All servers deleted, hit enter to continue"
    raw_input()

for x in range(number_of_runs):
    print "Server: %d" % x
    worked, return_value = startServer()
    print return_value
