import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
#object of ChromeOptions
import pathlib
import os
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def updatefangraphs(link='https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=rfangraphsdc', path=r'hitters', debug=False):
    default_download_directory=str(pathlib.Path().absolute() / path)
    #print(default_download_directory+"/FanGraphs Leaderboard.csv")
    
    if os.path.exists(default_download_directory+"/FanGraphs Leaderboard.csv"):
        os.remove(default_download_directory+"/FanGraphs Leaderboard.csv")
    caps = DesiredCapabilities().CHROME
    caps["pageLoadStrategy"] = "eager"  #  interactive

    op = webdriver.ChromeOptions()
    op.add_argument('--no-sandbox')
    op.add_argument('--disable-dev-shm-usage')
    op.add_argument('--disable-gpu')
    #add option
    if debug == False:
        op.add_argument('--headless')
    prefs = {
        "download.default_directory": default_download_directory,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "profile.default_content_settings.popups": 0,
    }
    op.add_experimental_option("prefs", prefs)
    #pass option to webdriver object

    driver = webdriver.Chrome(options=op,desired_capabilities=caps)
    driver.get(link)
    time.sleep(2)
    #Close header
    try:
        driver.find_element_by_xpath('//*[@id="ezmobfooter"]/span').click()
    except:
        print("An exception occurred")

    for attempt in range(4):
        try:
            driver.find_element_by_link_text('Export Data').click()
            time.sleep(2)
            break
        except:
            try:
                driver.find_element_by_xpath('//*[@id="ezmobfooter"]/span').click()
            except:
                try:
                    driver.find_element_by_link_text('Export Data').click()
                    time.sleep(2)
                    break
                except:
                    try:
                        driver.find_element_by_id('om-dmsmk5bir4naafnwsqbw').click()
                    except Exception as e:
                        if attempt < 3:
                            pass
                        else:
                            raise e