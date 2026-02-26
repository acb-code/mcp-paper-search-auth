# Process to set up authorization for MCP server

## run MCP server
- Set up code for server as in this repo
- run the dockerized mcp server from the directory with `docker-compose.yml`

```
docker compose up --build
```
Can use ` -d ` to run in the background, `docker compose logs -f` to view the logs in the terminal

This will bring up the MCP server on the localhost set in the code `:8000` in this case.

## Expose the localhost port to an https url

Now we will use ngrok (ngrok.com) to expose the localhost port on https (can also use cloudflared instead if desired). Go to ngrok.com and set up a free account, get an auth token and copy it.

In another terminal run
```
# one time setup only once done on a machine once, can skip
ngrok config add-authtoken <YOUR-NGROK-AUTH-TOKEN>
```
Run this to set up the https link to the localhost
```
ngrok http 8000
```

This will result in a url similar to below:
```
Forwarding                    https://<unique-string>.ngrok-free.dev -> http://localhost:8000
```

In what we have set up, the mcp server will be accessible at `https://<unique-string>.ngrok-free.dev/mcp`. We will use this later so copy this (and remember to add the `/mcp` if copy pasting from the terminal)

## Set up the authorization Step 1 of 3

We will use Auth0 (auth0.com) to handle authentication. Set up a free account at `auth0.com` I used my google account to sign in which might be best to get the google auth later to work (if you don't do this, additional steps might be required later).

- Create an API under Applications->APIs on the left column
    - Use the ngrok url + `/mcp` as the identifier (important to use this exactly), e.g., `https://<unique-string>.ngrok-free.dev/mcp`
    - give it a name, e.g., `pdf-search`
    - in the settings, turn on `Allow Offline Access`
    - in `Permissions`, add the things needed based on the mcp server code, with the current code this is just a permission for `read:papers`

- Under the Auth0 left column at the bottom (global) `Settings`, set the Default Audience to `https://<unique-string>.ngrok-free.dev/mcp`

## Set up the authorization Step 2 of 3

Now we need to create a client for ChatGPT/Claude.
- Go to Settings -> Apps (ChatGPT) or Connector (Claude) - note that for ChatGPT you first need to toggle on Developer mode in `Advanced`
- Add a new App (ChatGPT) or Connector (Claude), create a name, use the ngrok url with mcp `https://<unique-string>.ngrok-free.dev/mcp` as the server URL, and leave the Auth fields blank. Try to connect (it will fail).

## Set up the authorization Step 3 of 3

Now there should be a client for ChatGPT/Claude under Applications->Applications in Auth0

- We need to set this application to be first party rather than third party
    - Go to Applications->APIs->Auth0 Management API, under Application Access->Auth0 Management API(Test Application)->edit select `update:clients` as enabled
    - Go to Applications->APIs->Auth0 Management API->Test and copy the `"access_token"` value under the `Responses` section - we will use this as `<MANAGEMENT_API_TOKEN>` below
    - Go to Applications->Applications and get the `Client ID` for the ChatGPT or Claude entry, this will end up being `<LLM_CLIENT_ID>` below
    - From the top lect of the Auth0 page, get the Tenant ID, something like `dev-<random-characters>`, this will result in `<YOUR_TENANT>` below
    - run the command below in a new terminal copying in the client id and the access token
    ```
        curl -X PATCH "https://<YOUR_TENANT>.us.auth0.com/api/v2/clients/<LLM_CLIENT_ID>" \
    -H "Authorization: Bearer <MANAGEMENT_API_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"is_first_party": true}'
    ```
    - This should return a json which has `{"is_first_party": true}` somewhere in it, and if you look at the Applications->Applications in Auth0, the ChatGPT or Claude application should no longer have `THIRD-PARTY` written next to it.

- Now go to this Applications->Applications->ChatGPT or Claude application, go to the `Connections` tab and turn on the Google auth option (this option worked for me and the other option did not, there may be some other workaround without google auth, but I don't know it)
- Then go to Applications->APIs and open your mcp API that was created e.g., `pdf-search`. Go to the Application Access tab, for the ChatGPT or Claude application that was created and that we modified above, set access to `All` for both `User` and `Client`
- Go back to Applications->Applications->ChatGPT or Claude and copy the `Client ID` and `Client Secret`

## Finish setup in ChatGPT or Claude
- Delete the App (chatGPT) or Connector (Claude) that we created, and open a new one.
- Enter the name and description in the new one, use the url as before, e.g., `https://<unique-string>.ngrok-free.dev/mcp`
- This time enter the `Client ID` and `Client Secret` as copied from Auth0 to the fields for the App or Connector
- This should then connect successfully! Try in a new chat (confirming that the App or Connector is active): `Find a pdf with <example-string-from-one-paper-title>` and it with the current code, it should return the full title by querying the MCP server