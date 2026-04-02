2026-04-02 16:04:06,112 - INFO - -----search_jobs-----
2026-04-02 16:04:14,446 - INFO - -----get_job_links-----
2026-04-02 16:04:17,503 - ERROR - An error occurred: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#searchResultkensuu"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]
Traceback (most recent call last):
  File "C:\Working\ci-cd-example\scraping-team\mynavi20260402.py", line 147, in get_job_links
    all_num = self.cs.driver.find_element(By.CSS_SELECTOR, "#searchResultkensuu").text
              ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 816, in find_element
    return self.execute(Command.FIND_ELEMENT, {"using": by, "value": value})["value"]
           ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 446, in execute
    self.error_handler.check_response(response)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\errorhandler.py", line 232, in check_response
    raise exception_class(message, screen, stacktrace)
selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#searchResultkensuu"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]

2026-04-02 16:05:02,738 - INFO - -----search_jobs-----
2026-04-02 16:05:19,894 - ERROR - An error occurred: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#doSearch"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]
Traceback (most recent call last):
  File "C:\Working\ci-cd-example\scraping-team\mynavi20260402.py", line 68, in search_jobs
    search_button = self.cs.driver.find_element(By.CSS_SELECTOR, "#doSearch")
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 816, in find_element
    return self.execute(Command.FIND_ELEMENT, {"using": by, "value": value})["value"]
           ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 446, in execute
    self.error_handler.check_response(response)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\errorhandler.py", line 232, in check_response
    raise exception_class(message, screen, stacktrace)
selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#doSearch"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]

2026-04-02 16:05:19,898 - INFO - -----get_job_links-----
2026-04-02 16:05:22,928 - ERROR - An error occurred: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#searchResultkensuu"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]
Traceback (most recent call last):
  File "C:\Working\ci-cd-example\scraping-team\mynavi20260402.py", line 147, in get_job_links
    all_num = self.cs.driver.find_element(By.CSS_SELECTOR, "#searchResultkensuu").text
              ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 816, in find_element
    return self.execute(Command.FIND_ELEMENT, {"using": by, "value": value})["value"]
           ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\webdriver.py", line 446, in execute
    self.error_handler.check_response(response)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "c:\Working\ci-cd-example\.venv\Lib\site-packages\selenium\webdriver\remote\errorhandler.py", line 232, in check_response
    raise exception_class(message, screen, stacktrace)
selenium.common.exceptions.NoSuchElementException: Message: no such element: Unable to locate element: {"method":"css selector","selector":"#searchResultkensuu"}
  (Session info: chrome=146.0.7680.165); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#nosuchelementexception
Stacktrace:
	chromedriver!GetHandleVerifier [0x7ff7e21329c5+2ed785]
	chromedriver!GetHandleVerifier [0x7ff7e1e5a0d0+14e90]
	chromedriver!(No symbol) [0x7ff7e1bbdb2d]
	chromedriver!(No symbol) [0x7ff7e1c16b9e]
	chromedriver!(No symbol) [0x7ff7e1c16eac]
	chromedriver!(No symbol) [0x7ff7e1c66fe7]
	chromedriver!(No symbol) [0x7ff7e1c63b9b]
	chromedriver!(No symbol) [0x7ff7e1c09298]
	chromedriver!(No symbol) [0x7ff7e1c0a183]
	chromedriver!GetHandleVerifier [0x7ff7e215de0d+318bcd]
	chromedriver!GetHandleVerifier [0x7ff7e2158588+313348]
	chromedriver!GetHandleVerifier [0x7ff7e2179d7a+334b3a]
	chromedriver!GetHandleVerifier [0x7ff7e1e76785+31545]
	chromedriver!GetHandleVerifier [0x7ff7e1e7facc+3a88c]
	chromedriver!GetHandleVerifier [0x7ff7e1e63634+1e3f4]
	chromedriver!GetHandleVerifier [0x7ff7e1e637e6+1e5a6]
	chromedriver!GetHandleVerifier [0x7ff7e1e47e37+2bf7]
	KERNEL32!BaseThreadInitThunk [0x7fff4513e8d7+17]
	ntdll!RtlUserThreadStart [0x7fff45bac48c+2c]

