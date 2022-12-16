#--------------------------------------------------------------------------------------------------#
# SlackPost-Covid19.py: Covid19 Data Collection and Send a message to Slack                        #
#--------------------------------------------------------------------------------------------------#
#  AUTHOR: Yuhui.Seo        2022/12/09                                                             #
#--< CHANGE HISTORY >------------------------------------------------------------------------------#
#          Yuhui.Seo        2022/12/09 #001(Add config file)                                       #
#--< Version >-------------------------------------------------------------------------------------#
#          Python version 3.10.0                                                                   #
#--------------------------------------------------------------------------------------------------#
# Main process                                                                                     #
#--------------------------------------------------------------------------------------------------#
from urllib import request as r, parse
from datetime import date, datetime, timedelta
import os
import socket
import configparser

class SystemInfo:
    def system_info():
        hostname = socket.gethostname() # PC명
        # ip = socket.gethostbyname(hostname) #IP주소
        return hostname
    
    def get_file_directory():
        return (os.path.dirname(os.path.realpath(__file__)))
    
    def datetime_format(dates, format):
        match format:
            case 1:
                format = '%Y%m%d'                   # yyyyMMdd
            case 2:
                format = '%Y-%m-%d'                 # yyyy-MM-dd
            case 3:
                format = '%Y-%m-%d %H:%M:%S'        # yyyy-MM-dd HH:mm:ss
            case 4:
                format = '%Y%m%d%H%M%S'             # yyyyMMddHHmmss
            case 5:
                format = '%Y년%m월%d일 %H시%M분%S초' # yyyy년MM월dd일 HH시mm분ss초
            case _:
                format = '%Y%m%d%H%M%S'
        datetime_format = dates.strftime(format)
        return datetime_format


class ReadConfig:
    def __init__(self):
        dir = SystemInfo.get_file_directory()
        self.conf_file = dir + '\config.ini'
    
    def load_config(self):
        if os.path.exists(self.conf_file) == False:
            raise Exception('%s file does not exist. \n' % self.conf_file)
        else: 
            config = configparser.ConfigParser()
            config.read(self.conf_file, encoding = 'utf-8')
            print("Load Config : %s" % self.conf_file)
            return config


class FileAPI:
    def __init__(self, config):
        self.config = config
        self.Covid19 = Covid19API(config)
        self.directory = config.get('FILES', 'directory')
        self.file_name = config.get('FILES', 'file_name')
        self.exists_dir()

    def exists_dir(self):
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
    
    def set_date(self):
        start_date = date.today() - timedelta(days = 12)
        end_date = date.today()
        
        while start_date <= end_date:
            file_path = self.set_filepath(start_date)
            self.find_file(start_date, file_path)
            start_date += timedelta(days = 1)

    def set_filepath(self, dates):
        dates = SystemInfo.datetime_format(dates, 1)
        file_path = self.directory + '\\' + dates + '_' + self.file_name
        return file_path

    def find_file(self, dates, file_path):
        if not os.path.isfile(file_path):
            response_body = Covid19API.request_(self.Covid19, dates)
            self.save_xml(file_path, response_body)
        else:
            print('Xml file exists. : ' + file_path)

    def save_xml(self, file_path, xml):
        f = open(file_path, 'wb')
        f.write(xml)
        f.close()
        print('Xml file saved successfully. : ' + file_path)


class Covid19API:
    def __init__(self, config):
        config = config['COVID19'] 
        self.service_key = config['decoding_key']
        self.url = config['url']
    
    def set_covid19uri(self, dates):
        params = '?' + parse.urlencode({
            parse.quote_plus('serviceKey'): parse.unquote(self.service_key),       # ✔ 서비스키
            parse.quote_plus('pageNo'): '1',                                       # ✔ 페이지 번호
            parse.quote_plus('numOfRows'): '500',                                  # ✔ 한 페이지 결과 수
            parse.quote_plus('apiType'): 'xml',                                    # 데이터유형
            parse.quote_plus('std_day'): SystemInfo.datetime_format(dates, 2),     # 기준일자
            # parse.quote_plus('gubun'): '인천',                                    # 시도명
        })
        return params
        
    def request_(self, dates) :
        request = r.Request(self.url + self.set_covid19uri(dates))
        request.get_method = lambda: 'GET'
        response = r.urlopen(request)

        # status 200 OK (성공, Success)
        if response.status == 200:
            # response = r.urlopen(request).read().decode("utf-8")
            response_body = response.read()
            # print('response.url : ' + response.url) # redirection url
            # print(response.headers) # Date, Server, Content-Length, Connection, Content-Type
            return response_body
        else:
            print('status = ' + str(response.status) + ' error')


#--------------------------------------------------------------------------------------------------#
# Code Entry                                                                                       #
#--------------------------------------------------------------------------------------------------#
def code_start():
    config = ReadConfig.load_config(ReadConfig())
    file = FileAPI.set_date(FileAPI(config))

if __name__ == "__main__":
    code_start()