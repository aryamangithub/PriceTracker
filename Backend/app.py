import subprocess
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_cors import CORS
from requests import post
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen as uReq
import urllib.parse

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///database.db'

db = SQLAlchemy(app)

class ProductResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    img = db.Column(db.String(1000))
    url = db.Column(db.String(1000))
    price = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    search_text = db.Column(db.String(255))
    source = db.Column(db.String(255))

    def __init__(self, name, img, url, price, search_text, source):
        self.name = name
        self.url = url
        self.img = img
        self.price = price
        self.search_text = search_text
        self.source = source

class TrackedProducts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tracked = db.Column(db.Boolean, default=True)

    def __init__(self, name, tracked=True):
        self.name = name
        self.tracked = tracked

@app.route('/results', methods=['POST'])
def submit_results():
    results = request.json.get('data')
    search_text = request.json.get("search_text")
    source = request.json.get("source")

    for result in results:
        product_result = ProductResult(
            name=result['name'],
            url=result['url'],
            img=result["img"],
            price=result['price'],
            search_text=search_text,
            source=source
        )
        db.session.add(product_result)

    db.session.commit()
    response = {'message': 'Received data successfully'}
    return jsonify(response), 200


@app.route('/unique_search_texts', methods=['GET'])
def get_unique_search_texts():
    unique_search_texts = db.session.query(
        ProductResult.search_text).distinct().all()
    unique_search_texts = [text[0] for text in unique_search_texts]
    return jsonify(unique_search_texts)


@app.route('/results')
def get_product_results():
    search_text = request.args.get('search_text')
    print("requested search for ", search_text)
    results = ProductResult.query.filter_by(search_text=search_text).order_by(
        ProductResult.created_at.desc()).all()
    print("found ", len(results), " records")

    product_dict = {}
    for result in results:
        url = result.url
        if url not in product_dict:
            product_dict[url] = {
                'name': result.name,
                'url': result.url,
                "img": result.img,
                "source": result.source,
                "created_at": result.created_at,
                'priceHistory': []
            }
        product_dict[url]['priceHistory'].append({
            'price': result.price,
            'date': result.created_at
        })

    formatted_results = list(product_dict.values())

    return jsonify(formatted_results)


@app.route('/all-results', methods=['GET'])
def get_results():
    results = ProductResult.query.all()
    product_results = []
    for result in results:
        product_results.append({
            'name': result.name,
            'url': result.url,
            'price': result.price,
            "img": result.img,
            'date': result.created_at,
            "created_at": result.created_at,
            "search_text": result.search_text,
            "source": result.source
        })

    return jsonify(product_results)

@app.route('/start-scraper', methods=['POST'])
def start_scraper():
    url = request.json.get('url')
    search_text = request.json.get('search_text')
    main(url, search_text, "/results")
    response = {'message': 'Scraper started successfully'}
    return jsonify(response), 200


@app.route('/add-tracked-product', methods=['POST'])
def add_tracked_product():
    name = request.json.get('name')
    tracked_product = TrackedProducts(name=name)
    db.session.add(tracked_product)
    db.session.commit()

    response = {'message': 'Tracked product added successfully',
                'id': tracked_product.id}
    return jsonify(response), 200


@app.route('/tracked-product/<int:product_id>', methods=['PUT'])
def toggle_tracked_product(product_id):
    tracked_product = TrackedProducts.query.get(product_id)
    if tracked_product is None:
        response = {'message': 'Tracked product not found'}
        return jsonify(response), 404

    tracked_product.tracked = not tracked_product.tracked
    db.session.commit()

    response = {'message': 'Tracked product toggled successfully'}
    return jsonify(response), 200


@app.route('/tracked-products', methods=['GET'])
def get_tracked_products():
    tracked_products = TrackedProducts.query.all()

    results = []
    for product in tracked_products:
        results.append({
            'id': product.id,
            'name': product.name,
            'created_at': product.created_at,
            'tracked': product.tracked
        })

    return jsonify(results), 200


@app.route("/update-tracked-products", methods=["POST"])
def update_tracked_products():
    tracked_products = TrackedProducts.query.all()
    url = "https://amazon.ca"

    product_names = []
    for tracked_product in tracked_products:
        name = tracked_product.name
        if not tracked_product.tracked:
            continue

        command = f"python ./scraper/__init__.py {url} \"{name}\" /results"
        subprocess.Popen(command, shell=True)
        product_names.append(name)

    response = {'message': 'Scrapers started successfully',
                "products": product_names}
    return jsonify(response), 200

def search(metadata, page, search_text):
    print(f"Searching for {search_text} on {page.url}")
    search_field_query = metadata.get("search_field_query")
    search_button_query = metadata.get("search_button_query")

    if search_field_query and search_button_query:
        print("Filling input field")
        search_box = page.wait_for_selector(search_field_query)
        search_box.type(search_text)
        print("Pressing search button")
        button = page.wait_for_selector(search_button_query)
        button.click()
    else:
        raise Exception("Could not search.")

    page.wait_for_load_state()
    return page


def get_productsFromFlipkart(url, search_text):
    query_string = "/search?q="+search_text+ "&amp;sid=tyy%2C4io&amp;as=on&amp;as-show=on&amp;otracker=AS_QueryStore_HistoryAutoSuggest_0_2&amp;otracker1=AS_QueryStore_HistoryAutoSuggest_0_2&amp;as-pos=0&amp;as-type=HISTORY&amp;as-searchtext=sa"
    results = []
    containerClass = "_1YokD2 _3Mn1Gg"
    itemClass = "_1AtVbE col-12-12"
    itemNameClass = "_4rR01T"
    itemImageClass = "_396cs4"
    itemUrlClass= "_1fQZEK"
    priceClass = "_30jeq3 _1_WHN1"
    uClient = uReq(url+query_string)
    page_html = uClient.read()
    uClient.close()
    page_soup = soup(page_html, "html.parser")
    parentContainer = page_soup.findAll("div", { "class": containerClass})
    items = parentContainer[0].findAll("div", { "class": itemClass})
    for item in items:
        urls = item.findAll("a", {"class": itemUrlClass})
        if len(urls) == 0:
            continue
        itemNames = item.findAll("div", {"class": itemNameClass})
        prices = item.findAll("div", {"class": priceClass})
        price = prices[0].text
        price = price[1:]
        price = price.replace(",", "")
        imgs = item.findAll("img", {"class": itemImageClass})
        decodedSearchText = urllib.parse.quote_plus(search_text)
        print("decoded URL:", decodedSearchText)
        results.append({
            "url":urls[0]["href"],
            "name": itemNames[0].text,
            "img": imgs[0]["src"],
            "price": price,
            "source": "flipkart.com",
            "search_text": search_text
            # "search_text": decodedSearchText
        })
    print("result size: ", len(results))
    return results

def post_results(results, endpoint, search_text, source):
    headers = {
        "Content-Type": "application/json"
    }
    data = {"data": results, "search_text": search_text, "source": source}

    response = post("http://localhost:5000" + endpoint,
                    headers=headers, json=data)
    print("Status code:", response.status_code)


def main(url, search_text, response_route):
    results = get_productsFromFlipkart(url, search_text)
    post_results(results, response_route, search_text, url)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()
