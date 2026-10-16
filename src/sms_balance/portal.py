"""Drive one portal with Selenium: log in, handle OTP and pop-ups, read the balance."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from decimal import Decimal

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from sms_balance.config import Portal
from sms_balance.parsing import parse_amount

log = logging.getLogger(__name__)

DriverFactory = Callable[[bool], WebDriver]


def chrome(headless: bool = True) -> WebDriver:
    """Chrome via Selenium Manager (it downloads a matching driver automatically)."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def locator(selector: str) -> tuple[str, str]:
    """``xpath://...`` selects by XPath; anything else is a CSS selector."""
    if selector.startswith("xpath:"):
        return By.XPATH, selector.removeprefix("xpath:")
    return By.CSS_SELECTOR, selector


def read_balance(
    portal: Portal,
    driver_factory: DriverFactory = chrome,
    headless: bool = True,
    timeout: int = 15,
) -> Decimal:
    """Log in to ``portal`` and return its balance. The browser is always closed afterwards."""
    username, password = portal.credentials()
    if portal.otp and headless:
        log.warning("%s needs an OTP; use --headed so someone can type it", portal.name)
    driver = driver_factory(headless)
    try:
        wait = WebDriverWait(driver, timeout)
        driver.get(portal.url)

        wait.until(EC.presence_of_element_located(locator(portal.username_selector))).send_keys(
            username
        )
        password_field = wait.until(
            EC.presence_of_element_located(locator(portal.password_selector))
        )
        password_field.send_keys(password)
        if portal.submit_selector:
            wait.until(EC.element_to_be_clickable(locator(portal.submit_selector))).click()
        else:
            password_field.send_keys(Keys.ENTER)

        # Some portals pop a JavaScript alert after login.
        with suppress(NoAlertPresentException):
            driver.switch_to.alert.accept()

        if portal.otp:
            log.info("%s: waiting for the OTP to be entered in the browser", portal.name)
            WebDriverWait(driver, 60).until(EC.url_contains(portal.otp.page_url_contains))
            WebDriverWait(driver, portal.otp.timeout_seconds).until(
                EC.url_contains(portal.otp.done_url_contains)
            )

        for selector in portal.dismiss_selectors:
            clickable = EC.element_to_be_clickable(locator(selector))
            try:
                WebDriverWait(driver, 5).until(clickable).click()
            except TimeoutException:
                log.debug("%s: nothing to dismiss for %s", portal.name, selector)

        if portal.hover_selector:
            target = wait.until(EC.presence_of_element_located(locator(portal.hover_selector)))
            ActionChains(driver).move_to_element(target).perform()

        element = wait.until(EC.visibility_of_element_located(locator(portal.balance_selector)))
        balance = parse_amount(element.text)
        log.info("%s: balance %s %s", portal.name, balance, portal.currency)
        return balance
    finally:
        driver.quit()
