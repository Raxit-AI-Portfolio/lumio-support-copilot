---
doc_id: kb-cus-03-single-sign-on
title: Setting up single sign-on
access_group: customer
---

Single sign-on (SSO) lets your people sign in to Lumio with your company identity provider. It is available on the Business tier.

## Before you start

You need to be a workspace owner. You also need admin access to your identity provider. Check that your domain is verified in workspace settings under Security.

## Set-up steps

### In Lumio
Open workspace settings, choose Security, then Single sign-on. Copy the sign-in address and the entity name that Lumio shows.

### In your identity provider
Create a new application of type SAML. Paste the two values from Lumio. Map the email attribute to the user email. Download the metadata file.

### Back in Lumio
Upload the metadata file and press Test. Sign in with a test user. When the test passes, press Turn on.

## After it is on

Members sign in through the company page. Password sign-in is turned off for them. Owners keep a backup password sign-in so that a wrong set-up cannot lock everyone out.

## Common problems

If the test fails with a mismatch error, check the entity name. If users get a missing email error, check the attribute mapping.
