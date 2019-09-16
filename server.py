import sys
import tornado.websocket
import tornado.ioloop
import tornado.httpserver
import tornado.web
import json
import time
import math
import os
from global_vars import imu
import binascii
import global_vars as gl


# note: version string update should follow the updating rule
server_version = '1.1.0'

callback_rate = 50
class WSHandler(tornado.websocket.WebSocketHandler):
    count = 0
    magProgress = 0

    def open(self):
        self.callback = tornado.ioloop.PeriodicCallback(self.send_data, callback_rate)
        self.callback.start()
        self.callback2 = tornado.ioloop.PeriodicCallback(self.detect_status, 500)
        self.callback2.start()

    def detect_status(self):        
        if not imu.read(200):
            self.write_message(json.dumps({ "messageType": "queryResponse","data": {"packetType": "DeviceStatus","packet": { "returnStatus":1}}}))

    def send_data(self):
        if not imu.device_id:            
            self.write_message(json.dumps({ "messageType": "queryResponse","data": {"packetType": "DeviceStatus","packet": { "returnStatus":1}}}))
            time.sleep(1)
        if not imu.paused:
            d = imu.get_latest()
            self.write_message(json.dumps({ 'messageType' : 'event',  'data' : { 'newOutput' : d }}))               
        else:
            return False

    def on_message(self, message):
        global imu

        message = json.loads(message)
        # Except for a few exceptions stop the automatic message transmission if a message is received
        if message['messageType'] != 'serverStatus' and list(message['data'].keys())[0] != 'startLog' and list(message['data'].keys())[0] != 'stopLog':
            self.callback.stop()
            imu.pause()
        if message['messageType'] == 'serverStatus':
            if imu.logging:
                fileName = imu.logger.user['fileName']
            else:
                fileName = ''

            # Load the basic openimu.json(IMU application)
            with open('app_config/IMU/openimu.json') as json_data:
                imu.imu_properties = json.load(json_data)
            application_type = bytes.decode(imu.openimu_get_user_app_id())
            hw_version_str = application_type.split(' ')[1]  
            # application_type = imu.device_id

            # load application type from firmware 
            try:
                if imu.paused == 1 and not imu.openimu_get_user_app_id() == None:                                      
                    # Compass application
                    if 'Compass'in application_type:
                        with open('app_config/Compass/openimu.json') as json_data:
                            imu.imu_properties = json.load(json_data)
                        imu.imu_properties['userConfiguration'][3]['options'] = ['z1','s1','c1']
                        js_version_str = imu.imu_properties['app_version'].split(' ')[2]
                        imu.openimu_version_compare(hw_version_str,js_version_str)
                    # INS application
                    elif 'INS'in application_type:
                        with open('app_config/INS/openimu.json') as json_data:
                            imu.imu_properties = json.load(json_data)
                        imu.imu_properties['userConfiguration'][3]['options'] = ['z1','a1','a2','s1','e1','e2']
                        js_version_str = imu.imu_properties['app_version'].split(' ')[2]
                        imu.openimu_version_compare(hw_version_str,js_version_str)
                    # VG_AHRS application
                    elif 'VG_AHRS' in application_type:
                        with open('app_config/VG_AHRS/openimu.json') as json_data:
                            imu.imu_properties = json.load(json_data)
                        imu.imu_properties['userConfiguration'][3]['options'] = ['z1','a1','a2','s1','e1']
                        js_version_str = imu.imu_properties['app_version'].split(' ')[2]
                        imu.openimu_version_compare(hw_version_str,js_version_str)
                    # Framework application
                    elif 'OpenIMU'in application_type:
                        with open('app_config/OpenIMU/openimu.json') as json_data:
                            imu.imu_properties = json.load(json_data)
                        imu.imu_properties['userConfiguration'][3]['options'] = ['z1']
                        js_version_str = imu.imu_properties['app_version'].split(' ')[2]
                        imu.openimu_version_compare(hw_version_str,js_version_str)
                    # # IMU application
                    # elif 'IMU'in application_type and not 'OpenIMU'in application_type:
                    #     with open('app_config/IMU/openimu.json') as json_data:
                    #         imu.imu_properties = json.load(json_data)
                    #         time.sleep(1)
                    #     imu.imu_properties['userConfiguration'][3]['options'] = ['z1','s1']  
                    #     js_version_str = imu.imu_properties['app_version'].split(' ')[2]
                    #     imu.openimu_version_compare(hw_version_str,js_version_str)
                    # # Lever application    
                    # elif 'StaticL'in application_type:
                    #     with open('app_config/Leveler/openimu.json') as json_data:
                    #         imu.imu_properties = json.load(json_data)
                    #     imu.imu_properties['userConfiguration'][3]['options'] = ['z1','s1','l1']
                    else:
                        print('no json file matched!')

                    self.write_message(json.dumps({ 'messageType' : 'serverStatus', 'data' : { 'serverVersion' : server_version, 'serverUpdateRate' : callback_rate,  'packetType' : imu.packet_type,
                                                                                                'deviceProperties' : imu.imu_properties, 'deviceId' : imu.device_id, 'logging' : imu.logging, 'fileName' : fileName }}))
                else:
                    self.write_message(json.dumps({ "messageType": "queryResponse","data": {"packetType": "DeviceStatus","packet": { "returnStatus":2}}}))
                    imu.pause()
            except Exception as e:
                # print(e)                 
                self.write_message(json.dumps({ "messageType": "queryResponse","data": {"packetType": "DeviceStatus","packet": { "returnStatus":2}}}))
                imu.pause()
        elif message['messageType'] == 'requestAction':
            if list(message['data'].keys())[0] == 'gA':                
                data = imu.openimu_get_all_param()

                # data[7]['value'] = data[3]['value'].strip(b'\x00'.decode())
                time.sleep(0.2)
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "gA" : data }}))
                # print('requesting ok ---------------{0}'.format(self.count))                
            elif list(message['data'].keys())[0] == 'uP':
                data = imu.openimu_update_param(message['data']['uP']['paramId'], message['data']['uP']['value'])
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "uP" : data }}))
            elif list(message['data'].keys())[0] == 'sC':
                imu.openimu_save_config()
                time.sleep(0.5)
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "sC" : {} }}))
            # added by dave, for connect page to show version
            elif list(message['data'].keys())[0] == 'gV':
                data = imu.openimu_get_user_app_id()
                self.write_message(json.dumps({ "messageType" : "completeAction", "data" : { "gV" : str(data) }}))
            elif list(message['data'].keys())[0] == 'startStream':                                
                imu.connect()
                self.callback.start()  
                self.callback2.stop()
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "startStream" : {} }}))
            elif list(message['data'].keys())[0] == 'stopStream':
                imu.pause()
                self.callback2.start()
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "stopStream" : {} }}))
            elif list(message['data'].keys())[0] == 'startLog' and imu.logging == 0: 
                data = message['data']['startLog']
                imu.start_log(data)
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "logfile" : imu.logger.name }}))
            elif list(message['data'].keys())[0] == 'stopLog' and imu.logging == 1: 
                imu.stop_log()                
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "logfile" : '' }}))
            # added by Dave, app download page
            elif list(message['data'].keys())[0] == 'upgradeFramework':
                fileName = message['data']['upgradeFramework']
                if imu.openimu_upgrade_fw_prepare(fileName):
                    while not imu.openimu_finish_upgrade_fw():
                        imu.openimu_upgrade_fw(fileName)
                        self.write_message(json.dumps({ "messageType" : "processAction", "data" : { "addr" : imu.addr, "fs_len": imu.fs_len }}))
                    imu.openimu_start_app()
                self.write_message(json.dumps({ "messageType" : "completeAction", "data" : { "upgradeFramework" : fileName }}))
        elif message['messageType'] == 'magAction':
            if (list (message['data'].values())[0] == 'start'):
                imu.magneticAlignCmd('start')
                self.magProgress = 1
                # print ('mag align started')
                self.write_message(json.dumps({"messageType": "magAction", "data": {"start": {}}}))
            elif (list(message['data'].values())[0] == 'abort'):
                time.sleep(2)
                imu.magneticAlignCmd('abort')
                self.magProgress = 0
                # print ('mag align aborted')
                self.write_message(json.dumps({"messageType": "magAction", "data": {"abort": {}}}))
                return

            elif (list(message['data'].values())[0] == 'status'):
                # status = openIMUMagneticAlign.status()
                if (self.magProgress == 1):
                    status = imu.magneticAlignCmd('status')

                    if status == 1:
                        time.sleep(1)
                        storedValue = imu.magneticAlignCmd('stored')
                        self.write_message(
                            json.dumps({"messageType": "magAction", "data": {"status": "complete", "value": storedValue}}))

                        return


                    self.write_message(json.dumps({"messageType": "magAction", "data": {"status": "incomplete"}}))

            elif (list(message['data'].values())[0] == 'save'):
                imu.magneticAlignCmd('save')
                time.sleep(1)
                self.magProgress = 0
                data = imu.openimu_get_all_param()
                self.write_message(json.dumps({"messageType": "magAction", "data": {"status": "saved","value":data}}))
                return




        # OLD CODE REVIEW FOR DELETION
        elif  0 and message['messageType'] == 'requestAction':
            # Send and receive file list from local server
            if list(message['data'].keys())[0] == 'listFiles':
                logfiles = [f for f in os.listdir('data') if os.path.isfile(os.path.join('data', f)) and f.endswith(".csv")]
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "listFiles" : logfiles }}))
            elif list(message['data'].keys())[0] == 'loadFile':
                print(message['data']['loadFile']['graph_id'])
                f = open("data/" + message['data']['loadFile']['graph_id'],"r")
                self.write_message(json.dumps({ "messageType" : "requestAction", "data" : { "loadFile" :  f.read() }}))

    def on_close(self): 
        if(imu.logging == 1):
            imu.stop_log() 
        imu.pause()
        self.callback.stop()
        self.callback2.stop()
        time.sleep(1.2)
        
        
        # try:
        #     os._exit(0)
        # except:
        #    print('Program is off.')

        return False

    def check_origin(self, origin):
        return True
 
if __name__ == "__main__":
    # Create IMU
    print("server_version:",server_version)
    try: 
        imu.find_device()    
        # Set up Websocket server on Port 8000
        # Port can be changed
        application = tornado.web.Application([(r'/', WSHandler)])
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(8000)        
        
        tornado.ioloop.IOLoop.instance().start()
    
    except KeyboardInterrupt:  # response for KeyboardInterrupt such as Ctrl+C
        print('User stop this program by KeyboardInterrupt! File:[{0}], Line:[{1}]'.format(__file__, sys._getframe().f_lineno))
        os._exit(1)
    except Exception as e:
        print(e)    

    
