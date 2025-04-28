import requests
import csv


class CSVFetcher:
    """
    A simple class to fetch and parse CSV data from a remote URL.

    Features:
    - Fetches CSV data immediately (or manually if desired)
    - Access data as rows, dicts, or pandas DataFrame
    - Save the fetched CSV to a local file
    - Reload the data if needed
    """

    def __init__(self, url, auto_fetch=True):
        """
        Initializes the CSVFetcher.

        Args:
            url (str): URL of the CSV file to fetch.
            auto_fetch (bool): If True, fetch CSV immediately upon creation.
        """
        self.url = url
        self.csv_reader = None
        self._raw_csv_data = None  # Store raw CSV content for reuse
        if auto_fetch:
            self.fetch()

    def fetch(self):
        """
        Fetches CSV content from the URL and parses it.
        """
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            self._raw_csv_data = response.content.decode("utf-8")
            self.csv_reader = csv.reader(self._raw_csv_data.splitlines(), delimiter=",")
        except requests.RequestException as e:
            print(f"Error fetching CSV from {self.url}: {e}")
            self.csv_reader = None
            self._raw_csv_data = None

    def reload(self):
        """
        Refetches the CSV from the URL.
        """
        self.fetch()

    def get_rows(self):
        """
        Returns:
            list: A list of rows from the CSV file.
        """
        if self.csv_reader is None:
            raise ValueError("No CSV data loaded. Did you call fetch()?")

        # csv.reader is an iterator, so we need to recreate it
        return list(csv.reader(self._raw_csv_data.splitlines(), delimiter=","))

    def get_header(self):
        """
        Returns:
            list: The header row (column names) from the CSV.
        """
        rows = self.get_rows()
        if rows:
            return rows[0]
        return []

    def as_dicts(self):
        """
        Returns:
            list of dict: Each row represented as a dictionary with headers as keys.
        """
        rows = self.get_rows()
        if not rows:
            return []
        header = rows[0]
        return [dict(zip(header, row)) for row in rows[1:]]

    def save_to_file(self, filename):
        """
        Saves the fetched CSV data to a local file.

        Args:
            filename (str): Path where the CSV should be saved.
        """
        if self._raw_csv_data is None:
            raise ValueError("No CSV data loaded. Did you call fetch()?")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self._raw_csv_data)
