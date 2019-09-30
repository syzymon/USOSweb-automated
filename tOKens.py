import os
import ruamel.yaml as yaml
import logging
import logging.config
import coloredlogs
import json
import datetime

from os.path import join, dirname

import yagmail
from dotenv import load_dotenv
from usos.authentication import Authentication, Credentials
from usos.data import DataController
from usos.web_driver import SeleniumDriver
from usos.notifications import Dispatcher
from usos.scraper import Scraper


class TokensScraper(Scraper):
    def _detect(self, destination: str) -> object:
        """Detects the template to import based on a given destination.

        :param destination: scraper-compatible destination path.
        :returns: an imported ScrapingTemplate.
        """
        module = "templates.scraping.course"
        logging.debug("Looking for '{}' class".format(destination))
        return self._import(module=module)

    def _process_results_parsed(self, data: dict) -> None:
        """Uploads parsed results to the data controller.

        :param data: entities sent from a ScrapingTemplate.
        """
        self.data_controller.upload(data)


class TokensDataController(DataController):
    def __init__(self, dispatcher: object, recipients: dict):
        super().__init__(dispatcher)
        self._recipients_dict = recipients

    @staticmethod
    def _get_param_from_full_url(full_url: str) -> str:
        position_indicator = "course_id="
        return full_url[
               full_url.find(position_indicator) + len(position_indicator):]

    def upload(self, item: dict) -> None:
        self._data.append(item)

    def analyze(self) -> None:
        """Analyzes the data stored in the temporary storage and passes
        the results to the notifications' dispatcher."""
        for subject_info in self._data:
            if subject_info['Wolne miejsca'] > 0:
                subject_info["mail_recipient"] = self._recipients_dict[
                    self._get_param_from_full_url(
                        subject_info.get("url"))]

                self.results.append(subject_info)

        if self.results:
            logging.info("Changes detected, passing onto dispatcher")
            self.dispatcher.send(self.results)
        else:
            logging.info("No changes have been detected")


def load_environmental_variables(file) -> bool:
    """Populates the environment with variables from a .env file.

    :param file: path to the file with environmental variables.
    :returns: ``True`` if variables have been successfuly loaded.
    """
    if os.path.isfile(file):
        dotenv_path = join(
            dirname(__file__), file)
        load_dotenv(dotenv_path)
        return True
    else:
        logging.error("Oops! Did you forget to setup your .env file? "
                      + "You can use the included .env.sample as a "
                      + "starting point for your configuration.")
        return False


def load_directions(filename) -> dict:
    data = ""
    if os.path.isfile(filename):
        try:
            with open(filename) as f:
                data = json.load(f)
                # data = " ".join(json.load(f))
                logging.info("'{}' - json fetched ".format(filename)
                             + "correctly")
        except IOError:
            logging.exception("Config file '{}' ".format(filename)
                              + "could not be opened")
    print(data)
    return data


def check_required_dirs() -> bool:
    """Checks whether the required directories were created."""
    required = ["data", "logs"]
    old_mask = os.umask(
        000)  # To make sure these dirs will receive all permissions
    for directory in required:
        if not os.path.exists(directory):
            os.makedirs(directory, 0o777)
    os.umask(old_mask)
    return True


def load_logging_setup(debug_mode: bool) -> None:
    """Initializes the logging configuration with pretty-printing for
    console users.

    This method does not replace the configuration of the logging.yaml
    file.

    :param debug_mode: whether to include DEBUG statements in the
        console output.
    """
    with open('logging.yaml', 'r') as stream:
        config = yaml.load(stream)

    logging.config.dictConfig(config)

    log_level = 'INFO'
    if debug_mode:
        log_level = 'DEBUG'

    coloredlogs.install(
        fmt=config["formatters"]["simple"]["format"],
        level=log_level)

    selenium_logger = 'selenium.webdriver.remote.remote_connection'
    selenium_logger = logging.getLogger(selenium_logger)
    selenium_logger.setLevel(logging.ERROR)


def clean_sent():
    time = None

    with open("./mail_counts.json", "r") as json_counts:
        mail_counts = json.load(json_counts)
        if mail_counts.get("time"):
            time = datetime.datetime.strptime(mail_counts["time"],
                                              '%Y-%m-%d %H:%M:%S.%f')

    if not time or datetime.datetime.utcnow() - time > datetime.timedelta(
            hours=1):
        with open("./mail_counts.json", "w") as json_counts:
            json.dump({
                "sent": {

                },
                "time": None
            }, json_counts)


def main() -> None:
    load_logging_setup(
        debug_mode=(os.environ['USOS_SCRAPER_DEBUG_MODE'] == "True"))

    web_driver = SeleniumDriver(
        headless=(os.environ['USOS_SCRAPER_WEBDRIVER_HEADLESS'] == "True"),
        executable_path=(os.environ.get('USOS_SCRAPER_WEBDRIVER_ABS_PATH', ""))
    )

    web_driver = web_driver.get_instance()

    credentials = Credentials(
        username=os.environ['USOS_SETTINGS_USERNAME'],
        password=os.environ['USOS_SETTINGS_PASSWORD'])

    authentication = Authentication(
        credentials=credentials,
        root_url=os.environ['USOS_SCRAPER_ROOT_URL'],
        web_driver=web_driver)

    notifications_dispatcher = Dispatcher(
        channels=os.environ['USOS_NOTIFICATIONS_STREAMS'],
        enable=(os.environ['USOS_NOTIFICATIONS_ENABLE'] == "True"),
        config_file=os.environ['USOS_NOTIFICATIONS_CONFIG_FILE'])

    personalized_destinations = load_directions(
        os.environ['USOS_SCRAPER_DESTINATIONS_FILE'])

    data = TokensDataController(
        dispatcher=notifications_dispatcher,
        recipients=personalized_destinations)

    scraper = TokensScraper(
        root_url=os.environ['USOS_SCRAPER_ROOT_URL'],
        destinations=" ".join(personalized_destinations.keys()),
        authentication=authentication,
        data_controller=data,
        web_driver=web_driver)

    scraper.run()
    clean_sent()
    data.analyze()


if __name__ == "__main__":
    if load_environmental_variables('tokens.env') and check_required_dirs():
        main()
