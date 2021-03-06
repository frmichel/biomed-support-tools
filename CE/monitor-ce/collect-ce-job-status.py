#!/usr/bin/python
# List all CEs supporting the given VO, and display different data about the CE: site name, waiting, 
# running jobs, available slots. The status is collected from the BDII (draining, closed), and from
# the GOCDB (downtime, not monitored, not in production).
# The data is read from 2 different BDII objects: the GLueCE (global CE perspective) and the VOView (VO perspective),
# in order to check differences and the choices that sites do about data they publish.
# The output is displayed in CSV format, sorted by site name.
#
# Author: F. Michel, CNRS I3S, biomed VO support
#
# ChangeLog:
# 1.0: initial version
# 1.1: retrieve the status from the GOCDB
# 1.2: 2012-07:25 - fix bugs in the LDAP queries, retrive the status from the service-status.py tool to get both the status
#      from the GOCDB and the BDII
# 1.3: 2012-11-08 - fix bug in the site: always set with the same value

import sys
import os
import commands
import re
from operator import itemgetter, attrgetter
from optparse import OptionParser

DEFAULT_TOPBDII = "cclcgtopbdii01.in2p3.fr:2170"

optParser = OptionParser(version="%prog 1.2", description="""List all CEs supporting the given VO, and
display different data about the CE (status, waiting and running jobs...), read from 2 different BDII objects: the GlueCE
and the VOView, in order to check differences and the choices that sites do about data they publish.
The output is displayed in CSV format.""")

optParser.add_option("--vo", action="store", dest="vo", default="biomed",
                     help="Virtual Organisation to query. Defaults to \"biomed\"")

optParser.add_option("--bdii", action="store", dest="bdii", default=DEFAULT_TOPBDII,
                     help="top BDII hostname and port. Defaults to \"" + DEFAULT_TOPBDII + "\"")

optParser.add_option("--limit", action="store", dest="limit", default=9999,
                     help="Max number of CE to check. Defaults to all (9999)")

optParser.add_option("--debug", action="store_true", dest="debug",
                     help="Add debug traces")

# -------------------------------------------------------------------------
# Definitions, global variables
# -------------------------------------------------------------------------

(options, args) = optParser.parse_args()
VO = options.vo
TOPBDII = options.bdii
MAX_CE = int(options.limit)
DEBUG = options.debug

ldapSearch = "ldapsearch -x -L -s sub -H ldap://%(TOPBDII)s -b mds-vo-name=local,o=grid "

attributes = "GlueCEStateStatus GlueCEImplementationName GlueCEImplementationVersion GlueCEStateTotalJobs GlueCEStateWaitingJobs GlueCEStateRunningJobs GlueCEStateFreeJobSlots GlueCEPolicyMaxTotalJobs GlueCEPolicyMaxWaitingJobs GlueCEPolicyMaxRunningJobs GlueCEStateWorstResponseTime GlueCEStateWorstResponseTime"
attributesGrep = "\"GlueCEStateStatus|GlueCEImplementationName|GlueCEImplementationVersion|GlueCEStateTotalJobs|GlueCEStateWaitingJobs|GlueCEStateRunningJobs|GlueCEStateFreeJobSlots|GlueCEPolicyMaxTotalJobs|GlueCEPolicyMaxWaitingJobs|GlueCEPolicyMaxRunningJobs|GlueCEStateWorstResponseTime|GlueCEStateWorstResponseTime\""

ldapCE = ldapSearch + "\'(&(ObjectClass=GlueCE)(GlueCEUniqueID=%(CE)s))\' " + attributes + " | egrep " + attributesGrep

ldapVOView = ldapSearch + "\'(&(ObjectClass=GlueVOView)(GlueChunkKey=GlueCEUniqueID=%(CE)s)(GlueCEAccessControlBaseRule=VO:%(VO)s))\' " + attributes + " | egrep " + attributesGrep

try:  
   os.environ["VO_SUPPORT_TOOLS"]
except KeyError: 
    print "Please set variable $VO_SUPPORT_TOOLS before calling " + sys.argv[0]
    sys.exit(1)


# -------------------------------------------------------------------------
# Function fillGlueObject
#    Fills the fields of an item in arrays GlueCE or GlueViewVO that must
#    be initialized first.
# -------------------------------------------------------------------------

def fillGlueObject(glueObject, attrib, value):
        if attrib == "GlueCEImplementationName":
            glueObject['ImplName'] = value.strip()
        if attrib == "GlueCEImplementationVersion":
            glueObject['ImplVer'] = value.strip()
        if attrib == "GlueCEStateTotalJobs":
            glueObject['Total'] = value.strip()
        if attrib == "GlueCEStateWaitingJobs":
            glueObject['Waiting'] = value.strip()
        if attrib == "GlueCEStateRunningJobs":
            glueObject['Running'] = value.strip()
        if attrib == "GlueCEStateFreeJobSlots":
            glueObject['FreeSlots'] = value.strip()
        if attrib == "GlueCEPolicyMaxTotalJobs":
            glueObject['MaxTotal'] = value.strip()
        if attrib == "GlueCEPolicyMaxWaitingJobs":
            glueObject['MaxWaiting'] = value.strip()
        if attrib == "GlueCEPolicyMaxRunningJobs":
            glueObject['MaxRunning'] = value.strip()
        if attrib == "GlueCEStateWorstResponseTime":
            glueObject['WRT'] = value.strip()
        if attrib == "GlueCEStateWorstResponseTime":
            glueObject['ERT'] = value.strip()

        # The status is ignored as already retrieved by the service-status.py tool
        #if attrib == "GlueCEStateStatus" and value.strip() != "Production":
        #    glueObject['Status'] = value.strip().lower()

# -------------------------------------------------------------------------
# Make the list of CE which status is not normal in GOCDB
# -------------------------------------------------------------------------

if DEBUG: print "Retreiving CE with a specific status in GOCDB:"
GOCDBCE = {}
status, output = commands.getstatusoutput("$VO_SUPPORT_TOOLS/service-status.py --nose --nowms --vo " + VO)
for line in output.splitlines():
    if line.find('|') != -1:
        service, host, status = line.rsplit('|')
        GOCDBCE[host] = status
        if DEBUG: print host + ": " + status

# -------------------------------------------------------------------------
# Make the list of CE from the BDII
# -------------------------------------------------------------------------

GlueCE = {}
listCE = []
status, output = commands.getstatusoutput("lcg-infosites --vo " + VO + " ce -v 4")

nbCE = 0
for line in output.splitlines():
    if ("CE     " not in line) and ("Service      " not in line) and ("----------" not in line):
        host, site = line.split()
        listCE.append(host)
        GlueCE[host] = {'Site': site, 'Status':'', 'ImplName':'', 'ImplVer':'', 
                        'Total':'', 'Waiting':'', 'Running':'', 'FreeSlots':'', 
                        'MaxTotal':'', 'MaxWaiting':'', 'MaxRunning':'', 'WRT':'', 'ERT':''}
    if nbCE > MAX_CE: break;
    nbCE += 1

# -------------------------------------------------------------------------
# For each object GlueCE, retrieve attributes about jobs and status
# -------------------------------------------------------------------------

for host in listCE:
    if DEBUG: print "Checking GlueCE " + host + "..."
    status, output = commands.getstatusoutput(ldapCE % {'TOPBDII': TOPBDII, 'CE': host})
    if len(output) != 0:

        # Read the GlueCE object attributes read from the ldap request
        for line in output.splitlines():
            attrib, value = line.split(":")
            fillGlueObject(GlueCE[host], attrib, value)

        # Add the status information read from the GOCDB database, if any
        for gocdbhost in GOCDBCE:
            if host.find(gocdbhost) != -1:
                if GlueCE[host]['Status'] != "": 
                    GlueCE[host]['Status'] += ", " + GOCDBCE[gocdbhost]
                else:
                    GlueCE[host]['Status'] += GOCDBCE[gocdbhost]
                break

# -------------------------------------------------------------------------
# For each object VOView, retrieve attributes about jobs
# -------------------------------------------------------------------------

VOView = {}
for host in listCE:
    if DEBUG: print "Checking VOView " + host + "..."
    status, output = commands.getstatusoutput(ldapVOView % {'TOPBDII': TOPBDII, 'CE': host, 'VO': VO})
    if len(output) != 0:
        VOView[host] = {'ImplName':'', 'ImplVer':'', 'Total':'', 'Waiting':'', 'Running':'', 'FreeSlots':'', 
                        'MaxTotal':'', 'MaxWaiting':'', 'MaxRunning':'', 'WRT':'', 'ERT':''}
        # Read the VOView object attributes read from the ldap request
        for line in output.splitlines():
            attrib, value = line.split(":")
            fillGlueObject(VOView[host], attrib, value)

# -------------------------------------------------------------------------
# Display the results
# -------------------------------------------------------------------------

def sortBySite(el1, el2):
    # el1 and el2 are tuples (key, value) returned by GlueCE.iteritems(). 
    # The key el1[0] is the CE hostname, while el1[1]['Site'] is used for sorting.
    if el1[1]['Site'] > el2[1]['Site']: return 1
    if el1[1]['Site'] < el2[1]['Site']: return -1
    return 0

# Sort CEs by site name
sortedGlueCE = sorted(GlueCE.iteritems(), sortBySite)

print "# Site; CE; ImplName; ImplVer; CE Total; VO Total; CE Waiting; VO Waiting; CE Running; VO Running; CE FreeSlots; VO FreeSlots; CE MaxTotal; VO MaxTotal; CE MaxWaiting; VO MaxWaiting; CE MaxRunning; VO MaxRunning; CE WRT; VO WRT; CE ERT; VO ERT; CE Status"
for host, detail in sortedGlueCE:
    sys.stdout.write(detail['Site'] + "; " + host + "; ")
    sys.stdout.write(detail['ImplName'] + "; " + detail['ImplVer'] + "; ")
    sys.stdout.write(detail['Total'] + "; " + VOView[host]['Total'] + "; ")
    sys.stdout.write(detail['Waiting'] + "; " + VOView[host]['Waiting'] + "; ")
    sys.stdout.write(detail['Running'] + "; " + VOView[host]['Running'] + "; ")
    sys.stdout.write(detail['FreeSlots'] + "; " + VOView[host]['FreeSlots'] + "; ")
    sys.stdout.write(detail['MaxTotal'] + "; " + VOView[host]['MaxTotal'] + "; ")
    sys.stdout.write(detail['MaxWaiting'] + "; " + VOView[host]['MaxWaiting'] + "; ")
    sys.stdout.write(detail['MaxRunning'] + "; " + VOView[host]['MaxRunning'] + "; ")
    sys.stdout.write(detail['WRT'] + "; " + VOView[host]['WRT'] + "; ")
    sys.stdout.write(detail['ERT'] + "; " + VOView[host]['ERT'] + "; ")
    sys.stdout.write(detail['Status'])
    print
