# Instagram scraper

## Setup
Install chromium webdriver(linux):
```
sudo apt install chromium-chromedriver
```
If other platform, check this [link](https://chromedriver.chromium.org/getting-started).

Create python virtual environment:
```
python3 -m venv instagram_scraper_env
source instagram_scraper_env/bin/activate
# install requirements
python -m pip install selenium==3.141.0 requests==2.24.0 coloredlogs==14.0 enlighten==1.6.0
```

## Run Example
```
python instascrape.py --url https://www.instagram.com/explore/locations/1322233317896731/masjid-e-nabwi-saw/ --visual --login <my.username> --password <my.password> --max-scrolls 10000 -o output.csv --tags hajj ramadan
```


## Usage

```
python instascrape.py -h

usage: instascrape.py [-h] [--url URL] [-t [TAGS [TAGS ...]]] [-l LOGIN]
                      [-p PASSWORD] [--max-scrolls MAX_SCROLLS] [-v]
                      [-o OUTPUT] [--no-images]

Instagram location and tag gathering tool. Usage ...

optional arguments:
  -h, --help            show this help message and exit
  --url URL             Instagram location url to start with
  -t [TAGS [TAGS ...]], --tags [TAGS [TAGS ...]]
                        Filter tag
  -l LOGIN, --login LOGIN
                        Instagram profile to connect to, in order to access
                        the instagram posts of the target account
  -p PASSWORD, --password PASSWORD
                        Password of the Instagram profile to connect to
  --max-scrolls MAX_SCROLLS
                        Maximum number of scrolls
  -v, --visual          Spawns Chromium GUI, otherwise Chromium is headless
  -o OUTPUT, --output OUTPUT
                        Output file
  --no-images           Tell webdriver not to load images, for faster surfing
```
