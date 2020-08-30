#!/usr/bin/env python3

from prometheus_client import start_http_server, Metric, REGISTRY
import time
import os
import re
import boto3
import datetime
import json, ast

# Try get the TAG_PROJECT env variable. If not defined, we will use the Scost
tagProject = os.getenv('TAG_PROJECT', 'Name')

# Try get the PORT env variable. If not defined, we will use the 9150
port = os.getenv('PORT', 9150)


def getCosts():
    # Create a boto3 connection with cost explorer
    client = boto3.client('ce')

    # Get the current time
    now = datetime.datetime.utcnow()

    # Set the end of the range to start of the current day
    end = datetime.datetime(
        year=now.year, month=now.month, day=now.day, hour=now.hour)

    # Subtract a day to define the start of the range
    start =  datetime.datetime(
        year=now.year, month=now.month, day=now.day, hour=0)

    # Convert them to strings
    start = start.strftime('%Y-%m-%dT%H:00:00Z')
    end = end.strftime('%Y-%m-%dT%H:00:00Z')

    print("Starting script searching by the follow time range")
    print(start + " - " + end)

    # Call AWS API to get costs
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start,
            'End': end
        },
        Granularity='HOURLY',
        Metrics=['BlendedCost'],
        GroupBy=[
            {
                'Type': 'TAG',
                'Key': 'Product'
            },
            {
                'Type': 'TAG',
                'Key': 'App'
            }
        ]
    )

    # Create an empty dictionary
    projectValues = []

    # Run the response and make a dictionary with tag name and tag value
    for project in response["ResultsByTime"]:

        groups = project["Groups"]

        if not groups or groups is None:
            continue

        for group in groups:
            objectValues = {}

            keys = group['Keys']
            product = keys[0]
            app = keys[1]
            product_value = product.split("Product$", 1)[1]
            app_value = app.split("App$", 1)[1]

            unincoded_product_value = ast.literal_eval(json.dumps(product_value))
            unincoded_app_value = ast.literal_eval(json.dumps(app_value))
          

            if (not unincoded_product_value or unincoded_product_value is None or unincoded_product_value == '') and (not unincoded_app_value or unincoded_app_value is None or unincoded_app_value == ''):
                print('ignoring current resource')
                continue

            amount = group['Metrics']['BlendedCost']['Amount']
            unincoded_cost_value = ast.literal_eval(json.dumps(amount))

            objectValues = { 
                "app": unincoded_app_value,
                "product": unincoded_product_value,
                "value": unincoded_cost_value
            }

            # Append the values in the directionary
            projectValues.append(objectValues)

        return projectValues

    return projectValues

# Start classe collector
class costExporter(object):

    def collect(self):

        # Expose the metric
        # Create header
        metric = Metric('aws_project_cost',
                        'Total amount of costs for project', 'gauge')

        # Run the retuned dictionary and expose the metrics
        for cost in getCosts():
            metric.add_sample('aws_project_cost', value=cost['value'],
                              labels={'app': cost['app'], 'product': cost['product']})

        # /Expose the metric
        yield metric


if __name__ == '__main__':

    start_http_server(port)

    metrics = costExporter()
    REGISTRY.register(metrics)

    while True:
        time.sleep(1)
