import asyncio
import random
import string
import time
from typing import Optional, Dict, List, Tuple
import requests
from colorama import Fore, Style, init
from faker import Faker
from datetime import datetime
from twocaptcha import TwoCaptcha
from concurrent.futures import ThreadPoolExecutor
import cloudscraper
from shareithub import HTTPTools, ASCIITools

ASCIITools.print_ascii_intro()

init(autoreset=True)

fake = Faker()

# Fungsi untuk menghasilkan User-Agent acak secara dinamis
def generate_random_user_agent():
    platform = fake.random_element(elements=('Windows NT 10.0', 'Windows NT 6.1', 'Macintosh; Intel Mac OS X', 'X11; Linux x86_64'))
    browser = fake.random_element(elements=('Chrome', 'Firefox', 'Safari', 'Edge', 'Opera'))
    version = fake.random_int(min=70, max=120)  # Versi browser antara 70 hingga 120
    user_agent = f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) {browser}/{version}.0.{fake.random_int(min=0, max=100)}.0 Safari/537.36"
    return user_agent

def log_step(message: str, type: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "info": Fore.LIGHTCYAN_EX,
        "success": Fore.LIGHTGREEN_EX,
        "error": Fore.LIGHTRED_EX,
        "warning": Fore.LIGHTYELLOW_EX
    }
    color = colors.get(type, Fore.WHITE)
    prefix = {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️"
    }
    print(f"{Fore.WHITE}[{timestamp}] {color}{prefix.get(type, '•')} {message}{Style.RESET_ALL}")

def animate_loading(message: str):
    for _ in range(3):
        print(f"{Fore.YELLOW}{message}...", end="\r")
        time.sleep(0.5)
        print(f"{Fore.YELLOW}{message}.  ", end="\r")
        time.sleep(0.5)
        print(f"{Fore.YELLOW}{message}.. ", end="\r")
        time.sleep(0.5)
        print(f"{Fore.YELLOW}{message}... ", end="\r")
        time.sleep(0.5)
    print(" " * len(message), end="\r")

class CaptchaConfig:
    WEBSITE_KEY = '0x4AAAAAAAx1CyDNL8zOEPe7'
    WEBSITE_URL = 'https://app.nodepay.ai/login'

class Service2Captcha:
    def __init__(self, api_key):
        self.solver = TwoCaptcha(api_key)
    
    async def get_captcha_token_async(self):
        result = await asyncio.to_thread(
            lambda: self.solver.turnstile(
                sitekey=CaptchaConfig.WEBSITE_KEY,
                url=CaptchaConfig.WEBSITE_URL
            )
        )
        return result['code']

class CaptchaServiceFactory:
    @staticmethod
    def create_service(service_name: str, api_key: str):
        if service_name.lower() == "2captcha":
            return Service2Captcha(api_key)
        raise ValueError(f"Unknown service: {service_name}")

class ApiEndpoints:
    BASE_URL = "https://api.nodepay.ai/api"
    
    @classmethod
    def get_url(cls, endpoint: str) -> str:
        return f"{cls.BASE_URL}/{endpoint}"
    
    class Auth:
        LOGIN = "auth/login"
        ACTIVATE = "auth/active-account"

class LoginClient:
    def __init__(self):
        self.faker = Faker()
        self.max_retries = 5

    async def _get_captcha_with_retry(self, captcha_service, step: str = "unknown") -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                log_step(f"Getting captcha token for {step} (attempt {attempt}/{self.max_retries})...", "info")
                token = await captcha_service.get_captcha_token_async()
                log_step("Captcha token obtained successfully", "success")
                return token
            except Exception as e:
                log_step(f"Captcha error on attempt {attempt}: {str(e)}", "error")
                if attempt == self.max_retries:
                    log_step(f"Failed to get captcha after {self.max_retries} attempts", "error")
                    raise
        return None

    async def login(self, email: str, password: str, captcha_service) -> Optional[str]:
        for attempt in range(1, self.max_retries + 1):
            try:
                log_step(f"Login attempt {attempt} of {self.max_retries}...", "info")
                
                captcha_token = await self._get_captcha_with_retry(captcha_service, "login")
                if not captcha_token:
                    continue
                
                json_data = {
                    'user': email,
                    'password': password,
                    'remember_me': True,
                    'recaptcha_token': captcha_token
                }
                
                response = await self._make_request(
                    method='POST',
                    endpoint=ApiEndpoints.Auth.LOGIN,
                    json_data=json_data
                )
                
                if response.get("success"):
                    access_token = response['data']['token']
                    log_step("Login successful", "success")
                    # Langsung lanjutkan dengan token yang didapatkan tanpa menyimpannya ke file
                    await self.process_account_with_token(access_token)
                    return access_token
                else:
                    log_step(f"Login failed: {response.get('msg', 'Unknown error')}", "error")
                    
                if attempt == self.max_retries:
                    return None
                
            except Exception as e:
                log_step(f"Login error on attempt {attempt}: {str(e)}", "error")
                if attempt == self.max_retries:
                    return None
        return None

    async def process_account_with_token(self, token: str):
        """
        Proses akun menggunakan token yang sudah didapatkan tanpa menyimpannya ke dalam file.
        """
        account_info = AccountInfo(token)
        await render_profile_info(account_info)  # Mulai proses dengan token yang sudah didapatkan

    async def _make_request(self, method: str, endpoint: str, json_data: dict) -> dict:
        headers = self._get_headers()
        url = ApiEndpoints.get_url(endpoint)

        try:
            response = await asyncio.to_thread(
                lambda: requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    timeout=30
                )
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            log_step(f"Request failed: {str(e)}", "error")
            return {"success": False, "msg": str(e)}

    def _get_headers(self) -> Dict[str, str]:
        return {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://app.nodepay.ai',
            'priority': 'u=1, i',
            'referer': 'https://app.nodepay.ai/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
        }

    def read_accounts_from_file(self, filename: str = "akun.txt") -> List[Dict[str, str]]:
        accounts = []
        try:
            with open(filename, "r") as file:
                for line in file:
                    email, password = line.strip().split()
                    accounts.append({"email": email, "password": password})
        except FileNotFoundError:
            log_step(f"File {filename} not found.", "error")
        except Exception as e:
            log_step(f"Error reading {filename}: {str(e)}", "error")
        return accounts


# Skrip kedua untuk proses ping
PING_INTERVAL = 5
RETRIES = 10

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": [
        "https://nw.nodepay.org/api/network/ping"
    ]
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}



    def reset(self):
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
            self.account_data = {}
                self.retries = 3


scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)


async def load_tokens():
    try:
        with open('token.txt', 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        log_step(f"Failed to load tokens: {e}", "error")
        raise SystemExit("Exiting due to failure in loading tokens")


async def call_api(url, data, account_info):
    headers = {
        "Authorization": f"Bearer {account_info.token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cors-site"
    }

    try:
        response = scraper.post(url, json=data, headers=headers, timeout=60)
        response.raise_for_status()
    except Exception as e:
        log_step(f"Error during API call for token {account_info.token}: {e}", "error")
        raise ValueError(f"Failed API call to {url}")

    return response.json()



def process_account(token):
    """
    Process a single account: Initialize proxies and start asyncio event loop for this account.
    """
    account_info = AccountInfo(token)
    asyncio.run(render_profile_info(account_info))


async def main():

    print(f"{Fore.MAGENTA}BOT NODEPAY TOKEN SCRAPE !!{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}SUPPORT MULTI AKUN !.\n{Style.RESET_ALL}")
    
    # Ask user for captcha service and API key
    service_choice = input(f"{Fore.YELLOW}Choose captcha service (1 for 2Captcha): {Style.RESET_ALL}")
    api_key = input(f"{Fore.YELLOW}Enter your 2Captcha API Key: {Style.RESET_ALL}")

    service_map = {
        "1": "2captcha"
    }

    try:
        captcha_service = CaptchaServiceFactory.create_service(service_map[service_choice], api_key)
        log_step("Captcha service initialized", "success")
    except Exception as e:
        log_step(f"Failed to initialize captcha service: {str(e)}", "error")
        return

    client = LoginClient()
    log_step("Starting login process...", "info")

    # Read accounts from file and process each
    accounts = client.read_accounts_from_file()
    if not accounts:
        log_step("No accounts found to process.", "error")
        return
    
    for account in accounts:
        email = account["email"]
        password = account["password"]
        log_step(f"Attempting login for {email}...", "info")
        token = await client.login(email, password, captcha_service)
        if token:
            log_step(f"Token obtained for {email}: {token}", "success")
            # Proses langsung dengan token yang didapatkan tanpa menyimpannya
            await render_profile_info(AccountInfo(token))

if __name__ == "__main__":
    asyncio.run(main())
