"""Defines various data structures."""


class ConfigObject:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
    ):
        self.base_url = base_url
        self.username = username
        self.password = password


test_str = """
SYSINFO,1.7.3,9559698,1,3,0,257,4,4,5
Time,n.a.,n.a.,n.a.,n.a.,CPU Temp,Redox,pH,Pumpe,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,Terassenlicht,n.a.,n.a.,Gartenlicht,pH minus,Chlor,Bachlauf,Poolpumpe,TASTER1,TASTER2,TASTER3,TASTER4,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,n.a.,Cl Rest,pH- Rest,pH+ Rest,Cl consumption,pH- consumption,pH+ consumption
h,mV,mV,Bar,ppm,C,mV,pH,C,C,C,C,C,C,C,C,--,--,--,--,--,--,--,--,cm/s,--,--,--,--,--,--,--,--,--,--,--,%,%,%,ml,ml,ml
0,0,0,-0.400,6.00000,147.5,0.0,0.0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
1,0.0625,0.0625,0.0000125,0.000156,-0.00468750,0.0625,0.0078125,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,0.0625,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0.1,0.1,0.1,1,1,1
529,-44,-44,-44,-44,24878,14000,932,111,0,0,0,0,0,0,0,2,0,0,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,615,1000,0,0,0
"""


class GetStateData:

    def __init__(self, raw_data: str):
        self._raw_data = raw_data
        self.parse()

    def __str__(self):
        return self.raw_data

    def parse(self, raw_data: str | None = None):
        """Parse the raw data and populate the object's attributes."""
        if raw_data is None:
            raw_data = self.raw_data

        lines = raw_data.splitlines()
        sysinfo = lines[0].split(",")
        data_titles = lines[1].split(",")
        data_units = lines[2].split(",")
        data_offsets = lines[3].split(",")
        data_gain = lines[4].split(",")
        data_raw_values = lines[5].split(",")
        data_values = list[float]
        data_display_values = list[str]
        for i in data_raw_values.count():
            data_values[i] = (float(data_raw_values[i]) - float(data_offsets[i])) * float(data_gain[i])
            if len(data_units[i].strip()) > 0:
                data_display_values[i] = f"{data_values[i]:.2f} {data_units[i]}"
            else:
                data_display_values[i] = f"{data_values[i]}"

