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
import xml.etree.ElementTree as ET
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient            # requires: pip install slack_sdk

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
        self.Covid19 = Covid19API(config)
        self.config = config
        self.directory = config.get('FILES', 'directory')
        self.file_name = config.get('FILES', 'file_name')
        self.exists_dir()

    def exists_dir(self):
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)
    
    def set_date(self):
        file_list = []
        start_date = date.today() - timedelta(days = 12)
        end_date = date.today()
        
        while start_date <= end_date:
            file_path = self.set_filepath(start_date)
            self.find_file(start_date, file_path)
            file_list.append(file_path)
            start_date += timedelta(days = 1)
        
        return file_list

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

        # FIXME: 여러번 request할 때의 로직 수정 필요, Concurrent GET request, list of_urls
        # status 200 OK (성공, Success)
        if response.status == 200:
            # response = r.urlopen(request).read().decode("utf-8")
            response_body = response.read()
            return response_body
            # print('response.url : ' + response.url) # redirection url
            # print(response.headers) # Date, Server, Content-Length, Connection, Content-Type
        else:
            print('status = ' + str(response.status) + ' error')


class ReadXmlData:
    def __init__(self, file_list):
        self.stdDayList = [] # 기준일자
        self.defCntList = [] # 일별확진자수
        self.file_list = file_list
    
    def parse_data(self):
        dict = {}
        for file in self.file_list:
            tree = ET.parse(file)
            root = tree.getroot()
            result_code = root.find('header/resultCode').text
            incheon = root.find('body/items/item/incDec').text # TODO: 수정 필요

            for object in root.iter('item'):
                if result_code == '00' and (object.findtext('gubunEn') == 'Total'):
                    dict['누적확진자수'] = object.findtext('defCnt')
                    dict['시도명'] = object.findtext('gubun')
                    dict['시도명(영문)'] = object.findtext('gubunEn')
                    dict['전일대비확진자증감수'] = object.findtext('incDec')
                    dict['누적격리해제수'] = object.findtext('isolClearCnt')
                    dict['격리중환자수'] = object.findtext('isolIngCnt')
                    dict['지역발생수'] = object.findtext('localOccCnt')
                    dict['해외유입수'] = object.findtext('overFlowCnt')
                    dict['10만명당발생율'] = object.findtext('qurRate')
                    dict['기준일자'] = object.findtext('stdDay')
                    dict['사망자수'] = object.findtext('deathCnt')
                    
                    self.stdDayList.append(dict['기준일자'])
                    self.defCntList.append(dict['누적확진자수'])

                else:
                    raise Exception('%s 파일의 resultCode가 00이 아닙니다! \n' % file)
        
        return self.stdDayList, self.defCntList

class CreateChart:
    # matplotlib 모듈 사용하여 데이터 시각화
    import matplotlib.pyplot as plt
    import numpy as np
    import matplotlib.font_manager as fm

    # 한글 깨짐 해결
    font_list = [font.name for font in fm.fontManager.ttflist]
    if 'Malgun Gothic' in font_list:
        # Windows OS의 경우 폰트 설정
        plt.rcParams['font.family'] = 'Malgun Gothic' # 맑은고딕 폰트
    elif 'NanumGothic' in font_list:
        plt.rcParams['font.family'] = 'NanumGothic' # 나눔고딕 폰트
    # Mac OS의 경우 폰트 설정
    else:
        plt.rcParams['font.family'] = 'AppleGothic' # Apple Gothic


class SlackAPI:
    def __init__(self, token, config, now):
        # 슬랙 클라이언트 인스턴스 생성
        self.client = WebClient(token)
        self.hostname = SystemInfo.system_info()
        self.datetime = SystemInfo.get_current_datetime(now, 2)
        self.channel_id = config['SLACK']['channel_id']
        
    def post_Message(self, msg):
        try:
            response= self.client.chat_postMessage(
            channel= self.channel_id,
            text = '', # Slack 전송시 알람 메세지
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "text"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "text": self.hostname + ", " + self.datetime
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": msg
                    }
                }
            ]
        )
        except SlackApiError as e:
            print(e.response['error'])

#--------------------------------------------------------------------------------------------------#
# Code Entry                                                                                       #
#--------------------------------------------------------------------------------------------------#
def main():
    config = ReadConfig.load_config(ReadConfig())
    file_list = FileAPI.set_date(FileAPI(config))
    stdDayList, defCntList = ReadXmlData.parse_data(ReadXmlData(file_list))
    CreateChart(stdDayList, defCntList)

if __name__ == "__main__":
    main()