"""Helper functions for tests."""

from proconip.definitions import ConfigObject

BASE_URL = "http://127.0.0.1"
USERNAME = "admin"
PASSWORD = "admin"
GET_STATE_CSV = """
SYSINFO,1.7.3,9559698,1,3,0,257,4,4,5
Time,n.a.,n.a.,n.a.,n.a.,CPU Temp,Redox,pH,Pumpe,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,Terassenlicht,n.a.,n.a.,Gartenlicht,pH minus,Chlor,Bachlauf,Poolpumpe,TASTER1,TASTER2,TASTER3,TASTER4,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,Cl Rest,pH- Rest,pH+ Rest,Cl consumption,pH- consumption,pH+ consumption
h,mV,mV,Bar,ppm,C,mV,pH,C,C,C,C,C,C,C,C,--,--,--,--,--,--,--,--,cm/s,--,--,--,--,--,--,--,--,--,--,--,%,%,%,ml,ml,ml
0,0,0,-0.400,6.00000,147.5,0.0,0.0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
1,0.0625,0.0625,0.0000125,0.000156,-0.00468750,0.0625,0.0078125,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0.1,0.1,0.1,1,1,1
529,-44,-44,-44,-44,24878,14000,932,111,0,0,0,0,0,0,0,2,0,0,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,615,1000,0,0,0
"""
GET_DMX_CSV = """0,10,20,30,40,50,60,70,80,90,100,110,120,130,140,150
"""


def get_config_object():
    """Return a ConfigObject with the default values."""
    return ConfigObject(BASE_URL, USERNAME, PASSWORD)
