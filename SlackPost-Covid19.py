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
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.font_manager as fm
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient            # requires: pip install slack_sdk

class SystemInfo:
    def system_info():
        hostname = socket.gethostname() # PC명
        # ip = socket.gethostbyname(hostname) #IP주소
        return hostname
    
    def get_file_directory():
        return (os.path.dirname(os.path.realpath(__file__)))
    
    def datetime_format(date_time, format):
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
                format = '%Y년 %m월 %d일'            # yyyy년 MM월 dd일
            case 6:
                format = '%Y년%m월%d일 %H시%M분%S초'  # yyyy년MM월dd일 HH시mm분ss초
            case 7:
                format = '%Y/%m/%d'                 # YY/MM/dd/
            case _:
                format = '%Y%m%d%H%M%S'
        
        if type(date_time) is str:
            formatted = datetime.strptime(date_time, format).date()
        else:
            formatted = date_time.strftime(format)
        
        return formatted


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
    def __init__(self, config, PublicC19):
        self.PublicC19 = PublicC19
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
            response_body = Covid19API.http_get(self.PublicC19, dates)
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
        
    def http_get(self, params):
        try:
            request = r.Request(self.url + self.set_covid19uri(params))
            request.get_method = lambda: 'GET'
            response = r.urlopen(request)

            # FIXME: 여러번 request할 때의 로직 수정 필요, Concurrent GET request, list of_urls
            if response.status == 200:
                response_body = response.read()
                print(response.headers) # Date, Server, Content-Length, Connection, Content-Type
                return response_body
                # print('response.url : ' + response.url) # redirection url
                
        except Exception as e:
            print(e)
            return False


class ReadXmlData:
    def __init__(self, file_list):
        self.stdDayList = []    # 기준일자
        self.incDecList = []    # 전일대비확진자증감수
        self.file_list = file_list
    
    def parse_data(self):
        dict = {}
        for file in self.file_list:
            tree = ET.parse(file)
            root = tree.getroot()
            result_code = root.find('header/resultCode').text
            sido = 'Incheon'
            try:
                for data in root.findall('body/items/item'):
                    if result_code == '00' and (data.findtext('gubunEn') == 'Total'):
                        dict['누적확진자수'] = data.findtext('defCnt')
                        dict['시도명'] = data.findtext('gubun')
                        dict['시도명(영문)'] = data.findtext('gubunEn')
                        dict['전일대비확진자증감수'] = data.findtext('incDec')
                        # dict['누적격리해제수'] = data.findtext('isolClearCnt') # 데이터가 0만 들어옴
                        # dict['격리중환자수'] = data.findtext('isolIngCnt') # 데이터가 0만 들어옴
                        dict['지역발생수'] = data.findtext('localOccCnt')
                        dict['해외유입수'] = data.findtext('overFlowCnt')
                        # dict['10만명당발생율'] = data.findtext('qurRate')
                        
                        stdDay_str = data.findtext('stdDay')
                        dict['기준일자'] = stdDay_str[-5:].replace('-', '/')
                        
                        dict['사망자수'] = data.findtext('deathCnt')
                        
                        self.stdDayList.append(dict['기준일자']) # TODO: format MM/DD로 변경하고 싶음
                        self.incDecList.append(dict['전일대비확진자증감수'])
                        
                    if result_code == '00' and (data.findtext('gubunEn') == sido):
                        incDec = data.find('incDec').text
                        date = data.find('stdDay').text
                
            except Exception as e:
                raise e
        return self.stdDayList, self.incDecList


class ChartAPI:
    def __init__(self):
        self.today = SystemInfo.datetime_format(date.today(), 5)
        # matplotlib 한글깨짐 방지
        font_list = [font.name for font in fm.fontManager.ttflist]
        if 'Malgun Gothic' in font_list:
            plt.rcParams['font.family'] = 'Malgun Gothic' # Windows OS
        elif 'NanumGothic' in font_list:
            plt.rcParams['font.family'] = 'NanumGothic'
        else:
            plt.rcParams['font.family'] = 'AppleGothic' # Mac OS
        plt.rcParams['axes.unicode_minus'] = False # (-) 부호 깨짐 현상 방지
        
        
    def create_chart(self, stdDayList, incDecList):
        idx_List = list(range(len(stdDayList)))
        inc_dec = list(map(int, incDecList))
        
        plt.figure(figsize = (10,5)) # 그래프 크기 지정
        plt.suptitle('한국 코로나19 감염 추이', fontsize = 16, color = 'black')
        plt.title('기준일자 : '+ self.today, loc = 'right', fontsize = 12, color = 'gray')
        plt.xlabel('기준일자', fontsize = 13)
        plt.ylabel('확진자수(명)', fontsize = 13)
        
        # 꺾은 선 그래프 생성
        plt.plot(idx_List, inc_dec,
                linewidth = 3, color='hotpink', label = '확진자 수 추이', # 선 스타일 지정, 범례 추가
                marker = 'o', markersize = 6, markeredgecolor = 'hotpink', markerfacecolor = 'white') # 표식 추가, 표식 스타일 지정
        # 범례 표시 및 위치 지정
        plt.legend(loc = 'lower right')
        
        # x축 설정
        plt.xticks(idx_List, labels = stdDayList, rotation = 35) # rotation:각도
        
        # 그래프 값 표시
        for i in range(len(idx_List)):
            height = inc_dec[i]
            plt.text(idx_List[i], height, format(height, ','), ha = 'center', va = 'bottom', size = 11, color = 'black')
            
        # plt.savefig("경로명/그래프파일명.png", dpi = 100)
        plt.show()
        
        return plt


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
    PublicC19 = Covid19API(config)
    
    # 오늘날짜의 공공데이터가 있는지 확인, 없는 경우 xml 파일로 저장
    if Covid19API.http_get(PublicC19, date.today() + timedelta(days = 1)):
        file_list = FileAPI.set_date(FileAPI(config, PublicC19))

        # xml 파싱
        stdDayList, incDecList = ReadXmlData.parse_data(ReadXmlData(file_list))
        
        # Chart 생성
        ChartAPI.create_chart(ChartAPI(), stdDayList, incDecList)

if __name__ == "__main__":
    main()