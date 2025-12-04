#!/bin/bash

INSTANCES=`gcloud compute instances list \
    --project=$GOOGLE_CLOUD_PROJECT \
    --format='value(format("{0}:{1}", name,zone))'`
for INSTANCE in $INSTANCES; do
    NAME=${INSTANCE%%:*}
    ZONE=${INSTANCE#*:}
    gcloud compute instances remove-labels $NAME \
        --project=$GOOGLE_CLOUD_PROJECT \
        --zone=$ZONE \
        --labels=janitor-scheduled
    if [ $NAME == "gce-sbx-lnx-blob-01" ]; then
        gcloud compute instances add-labels $NAME \
            --project=$GOOGLE_CLOUD_PROJECT \
            --zone=$ZONE \
            --labels=janitor-scheduled=`date -d "yesterday 13:00" '+%Y-%m-%d'`        
    fi
done

gcloud compute instances list  \
    --project=$GOOGLE_CLOUD_PROJECT \
    --format='value(name, labels)'



