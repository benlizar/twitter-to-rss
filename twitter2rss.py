#!/usr/bin/python
import pickle, tweepy, urllib, pytz, logging
from feedgen.feed import FeedGenerator
from readability.readability import Document
from settings import *

logger = logging.getLogger('T2R')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(log_file)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %I:%M:%S %p %Z')
fh.setFormatter(formatter)
logger.addHandler(fh)

def load_buffer(fileName):
    try:
        buffered = pickle.load( open( fileName, "rb" ) )
    except Exception, e:
        logger.error(e)
        logger.warn("[Buffer_Load_ERR]:  Unable to load tweets from buffered. It's possible that the script is running for the first time. In that case it will be generated at the end of the script")
        buffered =[]
    else:
        logger.info("Buffer loaded successfully with " + str(len(buffered)) + " tweets.")
    return buffered

def get_lastID(buffered):
    id_list =[]
    for tweet in buffered:
        id_list.append(tweet['id'])
    return max(id_list)

def parse_twitter(buffered, keys):
    try:
        auth = tweepy.OAuthHandler(twitter_keys['consumer_key'], twitter_keys['consumer_secret'])
        auth.set_access_token(twitter_keys['access_token'], twitter_keys['access_token_secret'])
        api = tweepy.API(auth)
        # If the authentication was successful, you should
        # see the name of the account print out
        logger.debug('Fetching feeds for twitter user: ' + api.me().name) 
    except Exception, e:
        logger.error(e)
        logger.critical('Unable to log in to twitter. Quitting')
        exit()
    

    try: # In case the script is running for the first time. fetch the 
        lastID = get_lastID(buffered)

    except Exception, e:
        logger.warn('Can not retreive last ID, retreiving last 200 tweets instead')
        pub = api.home_timeline(count=200) #fetch feeds without since ID   
        for i in pub:
            parse_tweet(i)

    else:
        logger.debug("Will fetch tweets since tweet ID " + str(lastID))
        for i in tweepy.Cursor(api.home_timeline, since_id=str(lastID)).items(): 
            parse_tweet(i)
                # old code:  pub = api.home_timeline(count=200, since_id=str(lastID) ) #fetch feeds from the last ID
           
    return buffered

def parse_tweet(i):
    tweet ={}
    s = i.entities['urls']
    if len(s) > 0: # Check if tweet has a url
        urls = s[0]
        tweet['url'] = urls['expanded_url']
        
        try:
            html = urllib.urlopen(tweet['url']).read()
            tweet['readable_title'] = Document(html).title().encode('utf-8')
            tweet['readable_article'] = Document(html).summary().encode('utf-8')
        except Exception, e:
            logger.error(e)

        else:
            tweet['text'] = i.text.encode('utf-8')
            tweet['screen_name'] = i.user.screen_name
            tweet['profile_image_url'] = i.user.profile_image_url
            tweet['user_name'] = i.user.name
            tweet['user_url'] = i.user.url
            tweet['id'] = i.id
            tweet['id_str'] = i.id_str
            tweet['created_at'] = i.created_at
            
            try:
                logger.debug(tweet['id_str'].decode('utf-8', 'replace') + ' : @' + tweet['screen_name'].decode('utf-8', 'replace') + ' : ' + tweet['text'].decode('utf-8', 'replace'))
            except Exception, e:
                logger.error(e)
            
            try: #adding tweet context on top of the parsed article
                article_header =  '<img src="'.decode('utf-8') + tweet['profile_image_url'].decode('utf-8') + '" alt="'.decode('utf-8') + tweet['screen_name'].decode('utf-8') + '" /><p><strong>'.decode('utf-8') + tweet['user_name'].decode('utf-8') + ': </strong>'.decode('utf-8') + tweet['text'].decode('utf-8') +'</p>'.decode('utf-8')
            except Exception, e:
                logger.error(e)
            else:
                tweet['readable_article'] = article_header.encode('utf-8') + tweet['readable_article']

            buffered.insert(0, tweet)
            del buffered[feed_item_limit:] #pruning the feed to a maximum number of feeds.
            pickle.dump( buffered, open( buffer_file, "wb" ) )
            

def generateFeeds(buffered, meta):
    utc = pytz.utc
    fg = FeedGenerator()
    fg.id(meta['id'])
    fg.title(meta['title'])
    fg.author(meta['author'])
    fg.subtitle(meta['subtitle'])
    fg.link( href=meta['link'], rel='self' )
    fg.language(meta['language'])

    for tweet in buffered:
        fe = fg.add_entry()
        fe.id(tweet['url'].decode('utf-8'))
        fe.published(utc.localize(tweet['created_at']).astimezone(pytz.timezone(locale)))
        fe.link = tweet['url'].decode('utf-8')
        fe.guid(tweet['url'].decode('utf-8'))
        fe.title(tweet['readable_title'].decode('utf-8'))
        fe.description(tweet['readable_article'].decode('utf-8'))
        try:
            fe.author({'name': tweet['user_name'].decode('utf-8'), 'email':tweet['user_url'].decode('utf-8')})
        except Exception, e:
            logger.error(e)
            fe.author({'name': 'a', 'email':'a@a.com'})
       
    return fg                    

def write_rss(feedGenerator, fileName): 
    logger.debug('Writing RSS file')
    try:
        feedGenerator.rss_file(rss_file) # Write the RSS feed to a file
    except Exception, e:
        logger.error(e)
    else:
        logger.info('RSS file ' + fileName + " written successfully.")

logger.info('Session Started')
buffered = load_buffer(buffer_file)
parsed = parse_twitter(buffered, twitter_keys)
feed = generateFeeds(parsed, meta)
write_rss(feed, rss_file)
logger.info('Session Finished\n\n')