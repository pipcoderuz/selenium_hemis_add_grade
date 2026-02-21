# Imports required libraries from Selenium
from selenium import webdriver

# Initializing webdriver
driver = webdriver.Chrome()

# Navigating to google.com
driver.get("https://hemis.timeedu.uz/")

login_input = driver.find_element_by_id("formadminlogin-login")
password_input = driver.find_element_by_id("formadminlogin-password")

# Fetching title and printing it
print(driver.title)

# Closing webdriver instance
driver.quit()

# wm2CC3PdDXQMoQQsg3oGa0fcJwQXdlTo
# oraliq
# https://hemis.timeedu.uz/teacher/check-rating?id =11777

# yakuniy
# https://hemis.timeedu.uz/teacher/check-overall-rating?id =11778