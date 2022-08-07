from requests_html import HTMLSession
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.support.ui import WebDriverWait as wait
# from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup as Soup
import chromedriver_autoinstaller, time

from oauth2client.service_account import ServiceAccountCredentials
import gspread

def login(brwoser):
    # login button click
    brwoser.find_element(By.CSS_SELECTOR, "#main-application > header > div.wrapper > div > div > nav.top-nav > div > a").click()
    time.sleep(1)
    # teacher choice button click
    brwoser.find_element(By.CSS_SELECTOR, "#bifurcated-login-modal > div > div > div > div > section.modal-content > div > div.bifurcation > div:nth-child(4) > button").click()
    time.sleep(1)
    # put email & password
    brwoser.find_element(By.CLASS_NAME, "validated-input.input.email").send_keys(payload["e"])
    time.sleep(1)
    brwoser.find_element(By.CLASS_NAME, "validated-input.input.password").send_keys(payload["p"])
    time.sleep(1)
    # login button click
    brwoser.find_element(By.CLASS_NAME, "button.submit.-full-width").click()
    time.sleep(1)

def get_url(content_type, index):
    if content_type == "reading passages":
        url = f"https://www.readworks.org/find-content#!contentTab:search/q:/g:/t:/f:{index}/pt:A/features:/"

    if content_type == "paired texts":
        url = f"https://www.readworks.org/find-content#!contentTab:search/q:/g:/t:/f:{index}/pt:P/sr:false/features:/"

    if content_type == "article a day":
        url = f"https://www.readworks.org/find-content#!contentTab:search/q:/g:/t:/f:{index}/pt:AAD/sr:false/features:/"

    return url

def get_links(content_type):
    session1 = HTMLSession()
    session2 = HTMLSession()
    first_url = get_url(content_type, index=0)
    res1 = session1.get(first_url)
    res1.html.render(retries=8, wait=3.0, sleep=1)

    last_page = int(res1.html.find(".pagination-item")[-1].text)
    session1.close()

    links = list()
    for i in range(0, last_page):
        url = get_url(content_type, index=i)
        res2 = session2.get(url)
        res2.html.render(retries=8, wait=1.0, sleep=1)
        
        links_per_page = res2.html.find("div.articles")[0].absolute_links
        links += list(links_per_page)
        print(f"{i+1} / {last_page} page completed")
    
    session2.close()
    return links

def get_data(link, content_type):
        time.sleep(5)
        # html = brwoser.page_source -> html before js rendering
        html = brwoser.execute_script('return document.body.innerHTML')

        # parser
        soup = Soup(html, "html.parser")

        result = list()

        try:
            title = soup.select_one(".main-header-title").text.strip()
        except:
            title = ""
        
        try:
            thumbnail_image = soup.select_one("figure.image > img")["src"]
        except:
            thumbnail_image = ""
        
        try:
            topics = soup.select_one("h3.topics").text.strip()
        except:
            topics = ""
        
        try:
            grade = soup.select("section.article-single-meta.-stats > div > ul > li")[0].text.split(" ")[-1]
        except:
            grade = ""

        try:
            words = soup.select("section.article-single-meta.-stats > div > ul > li")[1].text.split(" ")[-1]
        except:
            words = ""

        try:
            lexile = soup.select("section.article-single-meta.-stats > div > ul > li")[2].text.split(" ")[-1].strip()
        except:
            lexile = ""        
        
        try:
            _type = soup.select("section.article-single-meta.-stats > div > ul > li")[3].text.split(" ")[-1]
        except:
            _type = ""

        text = ""
        for paragraph in soup.select("article > div > div > p"):
            text += f"#{paragraph.text}"

        if content_type == CONTENT_TYPE[1]:
            # title => common title change 
            common_title = title.split("\n")[0]

            # get sub title
            try:
                sub_title = soup.select_one("h1.rte").text.strip()
            except:
                sub_title = ""

            try:
                lexile = soup.select("section.article-single-meta.-stats > div > ul > li")[-1].text.split("range")[-1].strip()
            except:
                lexile = "" 

            try:
                words = soup.select_one("h1.rte").next_sibling.next_sibling.text.strip().split("(")[-1].split(" ")[0]
            except:
                words = ""

            result.extend([common_title, sub_title, link, thumbnail_image, grade, words, lexile, topics, text, _type])
            
            return result

        if content_type == CONTENT_TYPE[2]:
            # title => common title change 
            common_title = title.split("\n")[0]

            # get sub title
            try:
                sub_title = soup.select_one("h2.article-single-meta-title").text.split(":")[-1].strip()
            except:
                sub_title = ""

            result.extend([common_title, sub_title, link, thumbnail_image, grade, words, lexile, topics, text, _type])
            
            return result


        result.extend([common_title, sub_title, link, thumbnail_image, grade, words, lexile, topics, text, _type])

        return result

def scraping(links, content_type, retry=False):
    # count for gspread writing article a day text  
    count = 0
    for index_a, link in enumerate(links):
        brwoser.get(link)
        time.sleep(1)

        if index_a == 0:
            login(brwoser)
        
        result = get_data(link, content_type)

        if retry:
                write_gspread(retry_worksheet, index_a+1, result)
        
        if not retry:
            
            # reading passages => only one article
            if content_type == CONTENT_TYPE[0]:
                write_gspread(worksheet, index_a+1, result)
            
            # article a day => over six articles
            if content_type == CONTENT_TYPE[1]:
                articlel_links = brwoser.find_elements(By.CSS_SELECTOR, "a.article-title") 
                article_count = len(articlel_links)

                write_gspread(worksheet, count+1, result)

                for index_b, articlel_link in enumerate(brwoser.find_elements(By.CSS_SELECTOR, "a.article-title")[1:]):
                    articlel_link.click()

                    # have to move mouse for removing tooltip 
                    try:
                        ActionChains(brwoser).move_to_element(brwoser.find_element(By.CSS_SELECTOR, "h1.rte")).perform()
                    except:
                        pass

                    paired_result = get_data(brwoser.current_url, content_type) 
                    
                    write_gspread(worksheet, count+index_b+2, paired_result)

                count += article_count

            # paried texts => two articles
            if content_type == CONTENT_TYPE[2]:
                brwoser.find_elements(By.CLASS_NAME, "article-title")[-1].click()
                write_gspread(worksheet, (index_a*2)+1, result)

                paired_result = get_data(brwoser.current_url, content_type) 
                write_gspread(worksheet, (index_a*2)+2, paired_result)

        print(f"{index_a+1} / {len(links)} completed")


def connect_gspread(file_name):
    scope = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive',
    ]
    json_file_name = 'lxper.json'
    credentials = ServiceAccountCredentials.from_json_keyfile_name(json_file_name, scope)
    gc = gspread.authorize(credentials)
    sheets = gc.open(file_name)

    return sheets

def write_gspread(worksheet, index, result):
    last_alphabet = chr(65 + len(result))

    try:
        worksheet.update(f"A{index}:{last_alphabet}{index}", [result])
    except:
        print(f"{index} index got error while gspread writing")

# readworks account info
payload = {
    "e":"hojongjeon@lxper.com",
    "p":"dlwwlak9943!"
}

# install chromedriver
chromedriver_autoinstaller.install()

# options for browser
# brwoser maximization => login modal
brwoser_options = Options()
brwoser_options.add_argument("--start-maximized")
brwoser = webdriver.Chrome(options= brwoser_options)
brwoser.implicitly_wait(1000)

# google spread sheet
GSPREAD = "Reading Text Scraping"
CONTENT_TYPE = ["reading passages", "article a day", "paired texts"]
RETRY_SHEET = "retry"
sheets = connect_gspread(GSPREAD)  
worksheet = sheets.worksheet(f"ReadWorks {CONTENT_TYPE[1]}")
retry_worksheet = sheets.worksheet(RETRY_SHEET)

# select content type
# if you want to re scrape the failed links 
# fill column C at "retry" sheet with the links
failed_links = retry_worksheet.col_values(3)
if failed_links:
    scraping(failed_links, content_type=CONTENT_TYPE[1], retry=True)

else:
    links = get_links(content_type=CONTENT_TYPE[1])
    scraping(links, content_type=CONTENT_TYPE[1])
    
