#!/usr/bin/python

import ConfigParser,novaclient,sys,random,time
from novaclient.v1_1 import client

deleteServers = False

configName = "Ben"
if len(sys.argv) == 2:
	configName = sys.argv[1]
	while configName not in ['Admin','Ben','Delete']:
		print "Admin or Ben are the options"
		configName = raw_input().strip()
	if configName == 'Delete':
		deleteServers = True
		configName = "Ben"

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
Config = ConfigParser.ConfigParser()
Config.read('rc/config.ini')
novaconfig = ConfigSectionMap(configName)
novaobject = client.Client(novaconfig['nova_username'],novaconfig['nova_password'],novaconfig['nova_project_id'],novaconfig['nova_url'])

#serverItems = ['accessIPv4', 'accessIPv6', 'actions', 'addresses', 'created', 'diagnostics', 'flavor', 'hostId', 'id', 'image', 'is_loaded', 'key_name', 'links', 'metadata', 'name', 'networks', 'progress', 'status', 'tenant_id', 'user_id']

def returnServerStatus(server):
	try:
		server.get()
		status = server.status
	except Exception as crapola:
		if crapola == 'This request was rate-limited. (HTTP 413)':
			print "Rate limited: Waiting 5 seconds"
			time.sleep(5)
			return returnServerStatus(server)
	else:
		return status

def returnRandom(whatToRandomize,idonly=0):
	def randomize(list):
		return list[(random.randint(0,len(list)-1))]		
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

def returnOpen(whatToReturn,idonly=0):
	if whatToReturn == "floating_ip":
		for floating_ip in novaobject.floating_ips.list():
			if floating_ip.instance_id == None and idonly == 1:
				return floating_ip.ip
			elif floating_ip.instance_id == None:
				return floating_ip
		try:
			if len(novaobject.floating_ips.list()) < int(novaobject.quotas.get(novaconfig['os_auth_tenant']).floating_ips):
				if idonly == 1:
					print "creating ip"
					return novaobject.floating_ips.create().ip
					print "past creating ip"
				else:
					return novaobject.floating_ips.create()
		except Exception as crapola:
			if str(crapola) == "No more floating ips available. (HTTP 400)":
				return False
			elif str(crapola) == "Access was denied to this resource. (HTTP 403)":
				try:
					floating_ip = novaobject.floating_ips.create().ip
					return floating_ip
				except:
					return False
		return False

def getServerObjectFromName(serverName):
	for server in novaobject.servers.list():
		if server.name == serverName:
			return server
	return False


def shutdownInstances():
	try:
		for server in novaobject.servers.list():
			if returnServerStatus(server) == "PAUSED":
				server.unpause()
			while returnServerStatus(server) != "ACTIVE":
				time.sleep(2)
			print "Deleting %s"%server.id
			server.delete()
			print "Deleted"
		return 1,'yay'
	except Exception as crapola:
		return 0,crapola

def startServer():
	def bootRandomInstance():
		try:
			randomName = "test-%d-%d" % (time.time(), random.randint(0, 99999999))
			novaobject.servers.create(image=returnRandom('image',1),flavor=1,name=randomName)#returnRandom('flavor',1),name=randomName)
			print "Booted server %s"%randomName
			server = getServerObjectFromName(randomName)
			if server:
				while len(server.networks) == 0:
					time.sleep(3)
					server.get()
				floating_ip = returnOpen('floating_ip',1)
				if floating_ip:
					server.add_floating_ip(floating_ip)
					print "Added floating ip"
			server.get()
			return True,server
		except Exception as crapola:
			if str(crapola) == "This request was rate-limited. (HTTP 413)":
				print "rate limited, sleeping now"
				time.sleep(10)
			elif str(crapola) == "InstanceLimitExceeded: Instance quota exceeded. You cannot run any more instances of this type. (HTTP 413)":
				shutdownInstances()
			else:
				print str(crapola)
			return False,crapola
	
	def pauseInstance(server):
		try:
			server.pause()
			while returnServerStatus(server) == 'ACTIVE':
				time.sleep(2)
			print "Paused"
			return True,'yay'
		except Exception as crapola:
			return False,crapola
	
	def unpauseInstance(server):
		try:
			server.unpause()
			while returnServerStatus(server) != 'ACTIVE':
				time.sleep(2)
			print "Unpaused"
			return True,'yay'
		except Exception as crapola:
			return False,crapola
	
	def suspendInstance(server):
		try:
			server.suspend()
			while returnServerStatus(server) != 'SUSPENDED':
				time.sleep(2)
			print "Suspended"
			return True,'yay'
		except Exception as crapola:
			return False,crapola
	
	def resumeInstance(server):
		try:
			server.resume()
			while returnServerStatus(server) != 'ACTIVE':
				time.sleep(2)
			print "Resumed"
			return True,'yay'
		except Exception as crapola:
			return False,crapola
	
	def resizeInstance(server):
		try:
			server.resize(returnRandom('flavor',1))
			return True,crapola
		except Execrption as crapola:
			return False,crapola
	
	
	#def takeSnapshot(server):
	#	try:
	#		
	#		
	#	except Exception as crapola:
	#		return False,crapola
	
	perfect = 1
	startWorked,startReturn = bootRandomInstance()
	if startWorked:
		if not startWorked: print startReturn; perfect = 0;
		pauseWorked,pauseReturn = pauseInstance(startReturn)
		if not pauseWorked: print pauseReturn; perfect = 0
		unpauseWorked,unpauseReturn = unpauseInstance(startReturn)
		if not unpauseWorked: print unpauseReturn; perfect = 0
		suspendWorked,suspendReturn = suspendInstance(startReturn)
		if not suspendWorked: print suspendReturn; perfect = 0
		resumeWorked,resumeReturn = resumeInstance(startReturn)
		if not resumeWorked: print resumeReturn; perfect = 0
	else: 
		print startReturn; 
		perfect = 0;
		if startReturn == "This request was rate-limited. (HTTP 413)":
			print "Rate limited, sleeping for 10 seconds"
			time.sleep(10)
	if perfect == 0: return False,"Something went wrong with something";
	else: return True,"Seems to have ran through all operations smoothly";


if deleteServers:
	shutdownInstances()
	print "All servers deleted, hit enter to continue"
	raw_input()

for x in range(1000):
	print "Server: %d"%x
	worked,returnVal = startServer()
	print returnVal
	#worked,returnVal = bootRandomInstance()
	#if worked == 1:
	#	pauseWorked,pauseReturn = pauseInstance(returnVal)
	#	unpauseWorked,unpauseReturn = unpauseInstance(returnVal)
	#	suspendWorked,suspendReturn = suspendInstance(returnVal)
	#	resumeWorked,resumeReturn = resumeInstance(returnVal)
	#else:
	#	if str(returnVal) == "InstanceLimitExceeded: Instance quota exceeded. You cannot run any more instances of this type. (HTTP 413)":
	#		shutdownInstances()
	#	elif str(returnVal) == 'This request was rate-limited. (HTTP 413)':
	#		print returnVal
	#		time.sleep(10)
	#	else:
	#		print returnVal
