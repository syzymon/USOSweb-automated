import logging
from bs4 import BeautifulSoup

logging = logging.getLogger(__name__)


class ScrapingTemplate:
    """Scrapes the specific type of page by using predefined
    set of actions."""
    def __init__(self, web_driver: object) -> None:
        self.driver = web_driver
        self.results = None

    def get_data(self) -> object:
        """Returns the scraped and parsed data."""
        self._parse(soup=self._soup())

        logging.debug(self.results)
        self.results["parsed_results"]["url"] = self._get_url()
        return self.results

    def _get_url(self) -> str:
        """Get current course url"""
        return self.driver.current_url

    def _soup(self) -> object:
        """Generates a soup object out of a specific element
        provided by the web driver."""
        driver_html = self.driver.find_element_by_class_name("stretch")

        soup = BeautifulSoup(
            driver_html.get_attribute("innerHTML"),
            "html.parser")

        return soup

    def _parse(self, soup: object) -> None:
        """Initializes parsing of the innerHTML."""
        parser = Parser(soup=soup, web_driver=self.driver)
        self.results = {
            "module": __name__,
            "parsed_results": parser.get_parsed_results()
        }


class Parser:
    """Parses the provided HTML with BeautifulSoup."""
    def __init__(self, web_driver: object, soup: object) -> None:
        self.soup = soup
        self.driver = web_driver
        self.results = False

    def get_parsed_results(self) -> dict:
        """Returns the results back to the ScrapingTemplate."""
        def get_labeled_parameter(label: str):
            row = self.soup.find(text=label).parent
            return row.find_next_sibling().string

        handle = self.soup.find("span", {"class": "registered"})
        (current, maximum) = map(int, str(handle.parent.get_text()).split('/'))

        subject_name = get_labeled_parameter("Nazwa przedmiotu")

        try:
            classes_time = get_labeled_parameter("Termin")
        except:  # # FIXME
            classes_time = "default"

        self.results = {"Wolne miejsca": (maximum - current),
                        "Nazwa przedmiotu": subject_name,
                        "Termin": classes_time}
        return self.results
