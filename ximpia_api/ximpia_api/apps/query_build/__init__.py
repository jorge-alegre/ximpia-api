__author__ = 'jorgealegre'


def get_query_request(payload):
    """
    Get ElasticSearch query based on request search payload

    payload
    {
      "query": "cat",
      "filters": {
        "must": {
           name: value
        },
        "should": [
           {
             "field": "",
             "value": "",
             "rating": 5
           }
        ]
      },
      "excludes": {
        "user.id": 34
      },
      "sort": [
        "name",
        {
          "post_date": {
            "order": "asc"
          }
        }
      ],
      "group_by": [
          {
          },
          {
          }
      ]
    }

    {
      "query": {
          "fields": ['description']
          "value": "mine"
      },
      "filters": {
        "must": [
        ],
        "should": [
        ]
      }
    }

    :param payload: Dictionary with payload
    :return: ElasticSearch DSL Query as dictionary
    """
    query_dsl = {
        'query': {
            'filtered': {
            }
        }
    }
    # TODO: integrate ngrams, edgengrams. How? multimatch???
    # We could have pattern index settings to define chunks. StartEnd StartMiddleEnd
    # text_start, text_middle, text_end
    # query
    if 'query' in payload and isinstance(payload['query'], (str, unicode)):
        # query is string
        query_dsl['query']['filtered'] = {
            'match': {
                'text': {
                    "query": payload['query'],
                    "cutoff_frequency": 0.1,
                    "fuzziness": "AUTO"
                }
            }
        }
    elif 'query' in payload and isinstance(payload['query'], (tuple, list)):
        # query is a list of words: we search for keywords as phrases (AND) and any should match
        query_dsl['query']['filtered'] = {
            'bool': {
                'should': map(lambda x: {
                    'match': {
                        'text': {
                            "query": x,
                            "operator": "and",
                            "cutoff_frequency": 0.1,
                            "fuzziness": "AUTO"
                        }
                    }
                }, payload['query'])
            }
        }
    # filters
    if 'filters' in payload and 'must' in payload['filters'] and isinstance(payload['filters']['must'], dict):
        query_dsl['query']['filtered'].setdefault('filters', {})
        query_dsl['query']['filtered']['filters']['must'] = map(lambda x: {
            'term': {
                x[0]: x[1]
            }
        },
            payload['filters']['must'].items())
    elif 'filters' in payload and 'must' in payload['filters'] and isinstance(payload['filters']['should'], dict):
        query_dsl['query']['filtered'].setdefault('filters', {})
        query_dsl['query']['filtered']['filters']['should'] = map(lambda x: {
            'term': {
                x[0]: x[1]
            }
        },
            payload['filters']['should'].items())
    # excludes
    # sort
    # group_by
    return query_dsl