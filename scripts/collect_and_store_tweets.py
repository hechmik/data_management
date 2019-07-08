from pymongo import MongoClient
from pymongo.errors import PyMongoError
import tweepy
import json
import logging
from time import sleep
from random import randint, random



def load_twitter_credentials(keys_filename):
    """
    Load twitter credentials contained in the JSON file specified in keys_filename
    :param keys_filename: path of the JSON file containing the 4 twitter credentials
    :return: consumer_key, consumer_secret, access_token, access_token
    """
    with open(keys_filename) as api_credentials:
        api_twitter = json.loads(api_credentials.read())
        consumer_key = api_twitter['Twitter']["consumer_key"]
        consumer_secret = api_twitter['Twitter']["consumer_secret"]
        access_token = api_twitter['Twitter']["access_token"]
        access_secret = api_twitter['Twitter']["access_secret"]
        logging.debug("{}-{}-{}-{}".format(consumer_key, consumer_secret, access_token, access_secret))
        return consumer_key, consumer_secret, access_token, access_secret


def twitter_api_setup(consumer_key, consumer_secret, access_token, access_secret):
    """
    Login and create an API object that can be queried for obtaining tweets and other data
    :param consumer_key:
    :param consumer_secret:
    :param access_token:
    :param access_secret:
    :return:
    """
    logging.info("twitter_api_setup >>>")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)
    api = tweepy.API(auth,
                     wait_on_rate_limit=True,
                     wait_on_rate_limit_notify=True,
                     retry_count=1000,
                     retry_delay=60)
    logging.info("twitter_api_setup <<<")
    return api


def collect_and_store_tweets_from_query(api, query, since_date, until_date, mongo_collection, number_of_tweets = 200):
    """
    Download all the tweets related to the given query in the selected timerange.
    Store the results on the selected MongoDB collection
    :param api:
    :param query:
    :param since_date:
    :param until_date:
    :param mongo_collection:
    :param number_of_tweets:
    :return:
    """
    backoff_counter = 1
    logging.info("collect_and_store_tweets_from_query >>>")
    tweets = tweepy.Cursor(api.search,
                           q="{} -filter:retweets".format(query), #for reducing the number of calls
                           since=since_date,
                           until=until_date,
                           result_type="mixed" # in this way we are sure to collect all the popular tweets + some others
                           ).items(number_of_tweets)

    while True:
        try:
            tweet = tweets.next()

            logging.info("Query: {}, Tweet_date: {}".format(query, tweet.created_at))
            filtered_tweet = {
                "query": query,
                "text": tweet.text,
                "language": tweet.lang,
                "date": tweet.created_at,
                "username": tweet.user.name,
                "user_followers": tweet.user.followers_count,
                "user_location": tweet.user.location,
                "retweets": tweet.retweet_count,
                "likes": tweet.favorite_count,
            }
            mongo_collection.insert_one(filtered_tweet)
        except StopIteration:
            logging.info("Finished collecting and storing tweets for {}".format(query))
            break
        except PyMongoError:
            logging.error("Error on writing on MongoDB", exc_info=True)
        except tweepy.TweepError:
            logging.info("Reached Tweet limits, waiting for {} seconds".format(60 * backoff_counter))
            sleep(60 * backoff_counter)
            backoff_counter += 1
            continue


    logging.info("collect_and_store_tweets_from_query <<<")


def download_and_store_tweets_on_mongodb(api, list_of_queries, since_date, until_date, mongodb_collection):
    """
    This function generalize the download and storing of tweets on mongodb, so that the final user can use the tweepy API
    and MongoDB collection of his choice.
    :param api:
    :param list_of_queries:
    :param since_date:
    :param until_date:
    :param mongodb_collection:
    :return:
    """
    logging.info("download_and_store_tweets_on_mongodb >>>")
    for query in list_of_queries:
        logging.info("Working on: {}".format(query))
        collect_and_store_tweets_from_query(api, query, since_date, until_date, mongodb_collection)
        sleep(randint(30, 120))
    logging.info("download_and_store_tweets_on_mongodb <<<")


def download_and_store_tweets_on_default_mongodb_instance(keys_filename,
                                                          list_of_queries,
                                                          since_date,
                                                          until_date,
                                                          mongo_ip,
                                                          mongo_port):
    """
    This is the library main function.
    It enables to download multiple tweets in MongoDB (db = twitter, collection = game_tweets).

    :param keys_filename: path of the JSON file containing the 4 twitter credentials
    :param list_of_queries: list of strings that represents all the queries you're interested in downloading and storing
    :param since_date: starting date for downloading tweets in the format "YYYY-MM-DD"
    :param until_date: ending date for downloading tweets in the format "YYYY-MM-DD"
    :param mongo_ip: string that represents
    :param mongo_port:
    :return:
    """
    logging.info("download_and_store_tweets_on_default_mongodb_instance >>>")
    consumer_key, consumer_secret, access_token, access_secret = load_twitter_credentials(keys_filename)
    tweepy_api = twitter_api_setup(consumer_key, consumer_secret, access_token, access_secret)
    client = MongoClient(mongo_ip, mongo_port)
    db = client.dm_project
    tweet_games = db.twitter
    download_and_store_tweets_on_mongodb(tweepy_api, list_of_queries, since_date, until_date, tweet_games)
    logging.info("download_and_store_tweets_on_default_mongodb_instance <<<")
