import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
#object of ChromeOptions
import pathlib

def updatefangraphs(link='https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=rfangraphsdc', path=r'hitters'):
    default_download_directory=str(pathlib.Path().absolute() / path)

    op = webdriver.ChromeOptions()
    #add option
    op.add_argument('--enable-extensions')
    prefs = {
    "download.default_directory": default_download_directory,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    }
    op.add_experimental_option("prefs", prefs)
    #pass option to webdriver object

    driver = webdriver.Chrome(options=op)
    driver.get(link)

    #Close header
    try:
        driver.find_element_by_xpath('//*[@id="ezmobfooter"]/span').click()
    except:
        print("An exception occurred")

    #Download
    driver.find_element_by_link_text('Export Data').click()
