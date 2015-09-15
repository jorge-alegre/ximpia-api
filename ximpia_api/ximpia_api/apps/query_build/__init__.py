__author__ = 'jorgealegre'


def get_query_request(payload):
    """
    Get ElasticSearch query based on request search payload

    payload
    {
      "query": "cat",
      "filters": {
        "must": {
           name: value,
           name: {
             "gte": 23,
             "lte": 90
           }
        },
        "should": {
          name: value
        }
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

    Ranges:
    gte:2015-11-01
    gt:2015-11-01

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
        query_dsl['query']['filtered']['filters'].setdefault('bool', {})
        # We should have ranges as well
        must_list = []
        for field, value in payload['filters']['must'].items():
            if isinstance(value, dict) and ('gte' in value.keys() or 'gt' in value.keys() or 'lte' in value.keys()
                                            or 'lt' in value.keys()):
                must_list.append(
                    {
                        "range": {
                            field: value
                        }
                    }
                )
            else:
                must_list.append(
                    {
                        "term": {
                            field: value
                        }
                    }
                )
        query_dsl['query']['filtered']['filters']['bool']['must'] = must_list
    elif 'filters' in payload and 'must' in payload['filters'] and isinstance(payload['filters']['should'], dict):
        query_dsl['query']['filtered'].setdefault('filters', {})
        query_dsl['query']['filtered']['filters'].setdefault('bool', {})
        should_list = []
        for field, value in payload['filters']['should'].items():
            if isinstance(value, dict) and ('gte' in value.keys() or 'gt' in value.keys() or 'lte' in value.keys()
                                            or 'lt' in value.keys()):
                should_list.append(
                    {
                        "range": {
                            field: value
                        }
                    }
                )
            else:
                should_list.append(
                    {
                        "term": {
                            field: value
                        }
                    }
                )
        query_dsl['query']['filtered']['filters']['bool']['should'] = should_list
    # excludes
    if 'excludes' in payload:
        query_dsl['query']['filtered']['filters']['not'] = {
            "bool": {
                "must": map(lambda x: {
                    "term": {
                        x[1]: x[2]
                    }
                }, payload['excludes'].items())
            }
        }
    # sort
    # group_by: term aggregation
    return query_dsl