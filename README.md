# TransLiveCorpus

This repository contains the code for the livecorpus crawling pipeline and the TransLiveCorpus.

## Who created the TransLiveCorpus database and livecorpus app?

Will Hayworth (they/them), Google</br>
Lal Zimman (he/him or they/them), UC Santa Barbara, Dept. of Linguistics

## What is the TransLiveCorpus?

The TransLiveCorpus (TLC) consists of a database created by an application that takes semi-structured textual data and creates a structure that is friendly for the programmatic analysis of lexical variation and change in asynchronous interactional data.

The content of the TLC comes from four communities organized around different sorts of transgender people on LiveJournal.com that were in use in the 2000s: 
* FTM (for trans men and others on the transmasculine identity spectrum);
* MTF (for trans women and others on the transfeminine identity spectrum);
* TRANSGENDER (for trans-identified people in general);
* GENDERQUEER (for people whose gender identities and presentations go beyond the binary).

Included in the corpus are public posts made to these four communities between 2000 and 2017, as well as comments on those posts. Table 1 shows the data of each of the four communities in the corpus.

*Table 1: Breakdown of content in the TransLiveCorpus*

| Community	    | # of posts    | # of comments  | # of words     |
| ------------- | ------------- | -------------- | -------------- |
| FTM           |    19,643     |     207,579    |  17,034,982    |
| TRANSGENDER   |     5,930     |      34,498    |   3,586,914    |
| GENDERQUEER   |     3,167     |      18,560    |   1,833,638    |
| MTF           |     1,800     |      13,310    |   1,165,400    |
|               |               |                |                |
| TOTAL         |    30,540     |     273,947    |  23,620,934    |

The corpus database presents entries in chronological order, with comments interleaved with their source posts. The output structure of the TLC includes the following for each entry: 
* date, 
* textual content, 
* whether the entry is a post or a comment, 
* a post ID, which links comments to the posts on which they were made,
* a thread ID, which links comments in the same comment thread to one another,
* additional unstructured meta-data.

## How was TransLiveCorpus created?

TransLiveCorpus was created with livecorpus, a crawling pipeline built after its authors were unable to find an existing parser for LiveJournal that was both complete and usable. LiveJournal’s HTML is formatted for display in a browser, not for machine readability, so the raw data needed to be transformed significantly to make analysis tractable. We chose to use Google’s Cloud Platform because it allowed us to reserve and release computing resources easily, quickly, and cheaply and to take advantage of pre-existing managed services that also produced discrete, tested components to build upon.

The livecorpus crawler is written in Python 3 and runs on Google App Engine, which makes it easy to run code without much setup; it also scales up and down automatically. The crawler app fetches HTML pages from LiveJournal’s servers and parses them using BeautifulSoup. For pages that contain links to entries, the crawler extracts the links and enqueues them for further processing using Cloud Tasks. The Cloud Tasks push queue dispatches links to the crawler for parsing, ensuring that each entry is fetched and that our crawl is rate limited to comply with LiveJournal’s bt policy (no more than 5 connections per second). The parsed entries are stored in Cloud Firestore, a NoSQL document database, which uses a hierarchical data model matching LiveJournal’s structure in which communities have posts, posts have comments, and comments have replies.

More detail about the creation and use of livecorpus and TLC can be found in Zimman and Hayworth (2020a,b).

## What do I need to do to use the livecorpus app?

You will need to:
* Create a project on Google Cloud.
  * Change `trans-corpus` to your project ID in `store.py` and `task_queue.py`.
* Add your email address to the fetcher's `User-Agent` in `fetch.py`.

## Where can I read more about livecorpus and the TransLiveCorpus?

Zimman, Lal & Hayworth, Will (2020a). Lexical change as sociopolitical change in trans and cis identity labels: New methods for the corpus analysis of internet data. University of Pennsylvania Working Papers in Linguistics 25(2):Article 17. https://repository.upenn.edu/cgi/viewcontent.cgi?article=2076&context=pwpl

Zimman, Lal & Hayworth, Will (2020b). How we got here: Short-scale change in identity labels for trans, cis, and non-binary people in the 2000s. Proceedings of the Linguistic Society of America 5(1):499–513. https://journals.linguisticsociety.org/proceedings/index.php/PLSA/article/view/4728

## How should I cite the TransLiveCorpus?

Hayworth, Will & Zimman, Lal (2021). TransLiveCorpus. https://github.com/wsh/TransLiveCorpus.
