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
        self.dir_chart = config.get('FILES', 'dir_chart')
        self.file_name = config.get('FILES', 'file_name')
        self.mkdir()

    def exists_dir(self, directory):
        if not os.path.exists(directory):
            os.mkdir(directory)
    
    def mkdir(self):
        self.exists_dir(self.directory)
        self.exists_dir(self.dir_chart)
    
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
            
            # TODO : status가 200이지만 body가 없으면 에러나도록 if 조건 추가 필요
            tree = ET.parse(response)
            root = tree.getroot()
            body_check = root.find('body/items/item')
            
            # FIXME: 여러번 request할 때의 로직 수정 필요, Concurrent GET request, list of_urls
            if response.status == 200 and body_check:
                response_body = response.read()
                # print(response.headers) # Date, Server, Content-Length, Connection, Content-Type
                # print('response.url : ' + response.url) # redirection url
                return response_body
                
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
                        
                        self.stdDayList.append(dict['기준일자'])
                        self.incDecList.append(dict['전일대비확진자증감수'])
                        
                    if result_code == '00' and (data.findtext('gubunEn') == sido):
                        incDec = data.find('incDec').text
                        date = data.find('stdDay').text
                
            except Exception as e:
                raise e
        return self.stdDayList, self.incDecList


class ChartAPI:
    def __init__(self, config):
        # matplotlib 한글깨짐 방지
        font_list = [font.name for font in fm.fontManager.ttflist]
        if 'Malgun Gothic' in font_list:
            plt.rcParams['font.family'] = 'Malgun Gothic' # Windows OS
        elif 'NanumGothic' in font_list:
            plt.rcParams['font.family'] = 'NanumGothic'
        else:
            plt.rcParams['font.family'] = 'AppleGothic' # Mac OS
        plt.rcParams['axes.unicode_minus'] = False # (-) 부호 깨짐 현상 방지
        
        self.dir_chart = config.get('FILES', 'dir_chart')
        self.chart_name = config.get('FILES', 'chart_name')
        self.today = SystemInfo.datetime_format(date.today(), 5)
        self.chart_dt = SystemInfo.datetime_format(datetime.today(), 4)
        
    def create_chart(self, stdDayList, incDecList):
        idx_List = list(range(len(stdDayList)))
        inc_dec = list(map(int, incDecList))
        
        plt.figure(figsize = (10,6)) # 그래프 크기 지정
        plt.suptitle('한국 코로나19 감염 추이', fontsize = 16, color = 'black')
        plt.title('기준일자 : '+ self.today, loc = 'right', fontsize = 12, color = 'gray')
        plt.xlabel('기준일자', fontsize = 13)
        plt.ylabel('확진자수(명)', fontsize = 13)
        
        # 꺾은 선 그래프 생성
        plt.plot(idx_List, inc_dec,
                linewidth = 3, color='hotpink', label = '확진자 수 추이', # 선 스타일 지정, 범례 추가
                marker = 'o', markersize = 6, markeredgecolor = 'hotpink', markerfacecolor = 'white') # 표식 추가, 표식 스타일 지정
        # 범례 표시 및 위치 지정
        plt.legend(loc = 'best')
        
        # x축 설정
        plt.xticks(idx_List, labels = stdDayList, rotation = 35) # rotation:각도
        
        # 그래프 값 표시
        for i in range(len(idx_List)):
            height = inc_dec[i]
            plt.text(idx_List[i], height, format(height, ','), ha = 'center', va = 'bottom', size = 11, color = 'black')
        
        file = self.dir_chart + '\\' + self.chart_name + '_' + self.chart_dt + '.png'
        plt.savefig(file, dpi = 100)
        # plt.show()
        
        return file


class I18nAPI:
    def __init__(self):
        self.i18n = [
            {
                "IconUrl": "https://emoji.slack-edge.com/T017B0ZC4DB/gov_korea/a541d1740dc158e3.png",
                "en": {
                    "notification": "Today''s COVID-19 Notification in S.Korea",
                    "title": "COVID-19 Statistics",
                    "block_section_one_title": ":one: New Cases (Subtotal) : ",
                    "block_section_three_title": ":two: Daily Trend",
                    "attach_one_title": ":one: Daily New Cases",
                    "attach_one_field_one": "Subtotal (A+B)",
                    "attach_one_field_two": "Domestic (A)",
                    "attach_one_field_three": "Inflow (B)",
                    "attach_one_field_four": "Incheon",
                    "attach_one_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                    "attach_two_title": ":two: Infection Status",
                    "attach_two_field_two": "Confirmed",
                    "attach_two_field_four": "Death",
                    "attach_two_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                    "attach_three_title": ":two: Chart",
                    "plot_title": "Daily Trend of COVID-19, Republic of Korea",
                    "plot_data_one": "Confirmed",
                    "plot_xlabel": "Date",
                    "plot_ylabel": "Cases"
                    },
                "ko": {
                    "notification": "오늘의 코로나19 알림",
                    "title": "코로나19 통계정보",
                    "block_section_one_title": ":one: 추가확진 (소계) : ",
                    "block_section_three_title": ":two: 일자별 추이",
                    "attach_one_title": ":one: 추가확진",
                    "attach_one_field_one": "소계 (A+B)",
                    "attach_one_field_two": "국내 (A)",
                    "attach_one_field_three": "해외유입 (B)",
                    "attach_one_field_four": "인천",
                    "attach_one_footer": "<http://ncov.kdca.go.kr/|KDCA(Korean)",
                    "attach_two_title": ":two: 감염현황",
                    "attach_two_field_two": "누적확진",
                    "attach_two_field_four": "사망",
                    "attach_two_footer": "<http://ncov.kdca.go.kr/|KDCA(Korean)>",
                    "attach_three_title": ":two: 차트",
                    "plot_title": "한국의 코로나19 감염 추이",
                    "plot_data_one": "확진",
                    "plot_xlabel": "일자",
                    "plot_ylabel": "건수"
                    },
                "ja": {
                    "notification": "本日のコロナ19のお知らせ(韓国)",
                    "title": "コロナ19の統計情報",
                    "block_section_one_title": ":one: 追加確診 (小計) : ",
                    "block_section_three_title": ":two: 日付別推移",
                    "attach_one_title": ":one: 追加確診",
                    "attach_one_field_one": "小計 (A+B)",
                    "attach_one_field_two": "韓国国内 (A)",
                    "attach_one_field_three": "海外流入 (B)",
                    "attach_one_field_four": "仁川",
                    "attach_one_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                    "attach_two_title": ":two: 感染状況",
                    "attach_two_field_two": "累積確診",
                    "attach_two_field_four": "死亡",
                    "attach_two_footer": "<http://ncov.kdca.go.kr/en/|KDCA(English)>",
                    "attach_three_title": ":two: チャート",
                    "plot_title": "韓国のコロナ19感染推移",
                    "plot_data_one": "確診",
                    "plot_xlabel": "日付",
                    "plot_ylabel": "件数"
                    }
                }
            ]
        
    def set_i18n(self, lang):
        lang = self.i18n[0].get(lang)
        return lang
    
    
class SlackAPI:
    def __init__(self, config):
        token = config.get('SLACK', 'bot_token')
        # 슬랙 클라이언트 인스턴스 생성
        self.client = WebClient(token)
        self.channel_id = config.get('SLACK', 'channel_id')
        self.hostname = SystemInfo.system_info()
        self.datetime = SystemInfo.datetime_format(date.today(), 2)
        # self.file = file
    
    def post_Message(self, text):
        try:
            response= self.client.chat_postMessage(
            channel= self.channel_id,
            text = '텍스트입니다.',
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": text.get('title')
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
                        "text": text.get('block_section_one_title') + "몇건"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text.get('block_section_three_title')
                    }
                },
                {
                    "type": "divider"
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
    covid19 = Covid19API(config)
    slack = SlackAPI(config)
    
    # 1.정해진 기간의 공공데이터(xml file)가 있는지 확인, 없는 경우 저장
    if Covid19API.http_get(covid19, date.today() + timedelta(days = 1)):
        file_list = FileAPI.set_date(FileAPI(config, covid19))

        # 2.xml 파싱
        stdDayList, incDecList = ReadXmlData.parse_data(ReadXmlData(file_list))
        
        # 3.Chart 생성
        chart = ChartAPI.create_chart(ChartAPI(config), stdDayList, incDecList)

        # 4.slack 전송
        lang = ['en', 'ko', 'ja']
        for la in lang:
            text = I18nAPI.set_i18n(I18nAPI(), la)
            SlackAPI.post_Message(slack, text)
        
if __name__ == "__main__":
    main()