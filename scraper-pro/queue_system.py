import redis
from rq import Queue

redis_conn = redis.Redis(host='localhost', port=6379, db=0)

scrape_queue = Queue("scraper", connection=redis_conn)