---
doc_id: kb-cus-02-api-keys
title: Creating and managing API keys
access_group: customer
---

API keys let your own scripts talk to the Lumio API. Only workspace owners and admins can manage them.

## Creating a key

Open workspace settings, choose Developer, then choose New API key. Give the key a name that says what it is for. Pick a scope: read only or read and write. Lumio shows the secret value once. Copy it into your own secret store right away.

## Limits

A workspace can hold up to 10 active keys. Each key is limited to 100 requests per minute. Requests above the limit get a rate limit answer and should be retried after a short wait.

## Rotating a key

Create a new key, update your scripts, check they work, and then delete the old key. A deleted key stops working within one minute.

## If a key leaks

Delete the key at once from the Developer page. Then create a new one. Check the activity list on the Developer page for requests you do not recognize and open a ticket if you see any.

## Good habits

Never put a key in code that is shared or in a public place. Use one key per script so that you can remove one without breaking the others.
