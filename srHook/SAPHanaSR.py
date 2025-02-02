"""
# SAPHana
# Author:       Fabian Herschel, 2015
# License:      GNU General Public License (GPL)
# Copyright:    (c) 2015-2016 SUSE Linux GmbH
# Copyright:    (c) 2017-2022 SUSE LLC
"""
try:
    from hdb_ha_dr.client import HADRBase
except ImportError as e:
    print("Module HADRBase not found - running outside of SAP HANA? - {0}".format(e))
import os

"""
To use this HA/DR hook provide please add the following lines to your global.ini:
    [ha_dr_provider_SAPHanaSR]
    provider = SAPHanaSR
    path = /usr/share/SAPHanaSR
    execution_order = 1

    [trace]
    ha_dr_saphanasr = info
"""
fhSRHookVersion = "0.162.0"


try:
    class SAPHanaSR(HADRBase):

        def __init__(self, *args, **kwargs):
            # delegate construction to base class
            super(SAPHanaSR, self).__init__(*args, **kwargs)
            self.tracer.info("SAPHanaSR init()")

        def about(self):
            return {"provider_company": "SUSE",
                    "provider_name": "SAPHanaSR",  # class name
                    "provider_description": "Inform Cluster about SR state",
                    "provider_version": "1.0"}

        def srConnectionChanged(self, ParamDict, **kwargs):
            """ finally we got the srConnection hook :) """
            method = "srConnectionChanged"
            self.tracer.info("SAPHanaSR {0} {1}.srConnectionChanged method called with Dict={2}".format(fhSRHookVersion, self.__class__.__name__, ParamDict))
            # self.tracer.info("SAPHanaSR (%s) %s.srConnectionChanged method called with Dict=%s" % (fhSRHookVersion, self.__class__.__name__, ParamDict))
            # myHostname = socket.gethostname()
            # myDatebase = ParamDict["database"]
            mySystemStatus = ParamDict["system_status"]
            mySID = os.environ.get('SAPSYSTEMNAME')
            mysid = mySID.lower()
            myInSync = ParamDict["is_in_sync"]
            myReason = ParamDict["reason"]
            mySite = ParamDict["siteName"]
            self.tracer.info("SAPHanaSR {0}.srConnectionChanged mySystemStatus={1} mySID={2} myInSync={3} myReason={4}".format(self.__class__.__name__, mySystemStatus, mySID, myInSync, myReason))
            if mySystemStatus == 15:
                mySRS = "SOK"
            else:
                if myInSync:
                    # ignoring the SFAIL, because we are still in sync
                    self.tracer.info("SAPHanaSR (%s) %s.srConnectionChanged ignoring bad SR status because of is_in_sync=True (reason=%s)" % (fhSRHookVersion, self.__class__.__name__, myReason))
                    mySRS = ""
                else:
                    mySRS = "SFAIL"
            if mySRS == "":
                myMSG = "### Ignoring bad SR status because of is_in_sync=True ###"
                self.tracer.info("{0}.{1}() {2}\n".format(self.__class__.__name__, method, myMSG))
            elif mySite == "":
                myMSG = "### Ignoring bad SR status because of empty site name in call params ###"
                self.tracer.info("{0}.{1}() {2}\n".format(self.__class__.__name__, method, myMSG))
            else:
                myCMD = "sudo /usr/sbin/crm_attribute -n hana_%s_site_srHook_%s -v %s -t crm_config -s SAPHanaSR" % (mysid, mySite, mySRS)
                rc = os.system(myCMD)
                myMSG = "CALLING CRM: <{0}> rc={1}".format(myCMD, rc)
                self.tracer.info("{0}.{1}() {2}\n".format(self.__class__.__name__, method, myMSG))
                fallback_file_name = "../.crm_attribute.{0}".format(mySite)
                fallback_stage_file_name = "../.crm_attribute.stage.{0}".format(mySite)
                if rc == 0:
                    # cluster attribute set was successfull - delete pending fallback file, if existing
                    try:
                        os.remove(fallback_file_name)
                        self.tracer.info("new event - pending fallback file {0} deleted".format(fallback_file_name))
                    except FileNotFoundError:
                        pass
                else:
                    #
                    # FALLBACK
                    # sending attribute to the cluster failed - using fallback method and write status to a file - RA to pick-up the value during next SAPHanaController monitor operation
                    #
                    myMSG = "sending attribute to the cluster failed - using local file as fallback"
                    self.tracer.info("{0}.{1}() {2}\n".format(self.__class__.__name__, method, myMSG))
                    #
                    # cwd of hana is /hana/shared/<SID>/HDB00/<hananode> we use a relative path to cwd this gives us a <sid>adm permitted directory
                    #     however we go one level up (..) to have the file accessible for all SAP HANA swarm nodes
                    #
                    with open(fallback_stage_file_name, "w", encoding='utf-8') as fallbackFileObject:
                        fallbackFileObject.write("hana_{0}_site_srHook_{1} = {2}".format(mysid, mySite, mySRS))
                    #
                    # release the stage file to the original name (move is used to be atomic)
                    #      .crm_attribute.stage.<site> is renamed to .crm_attribute.<site>
                    #
                    os.rename(fallback_stage_file_name, fallback_file_name)
            return 0
except NameError as e:
    print("Could not find base class ({0})".format(e))
