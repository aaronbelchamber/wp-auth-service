# User Auth Guide

For anyone using an app built on this auth system (e.g. Fun Activities App).

## Logging in the first time

The first time you open the app, you'll be walked through connecting your
WordPress account — you don't need to do anything in advance, and you don't
need to visit any website yourself first.

**On phones/tablets:** a login screen opens inside the app itself. Log in
with your normal WordPress username and password, review what the app is
asking permission for, and approve it. You're taken straight back into the
app — you never leave it.

**On desktop:** the app opens your regular web browser to the same login
page. Log in and approve there, then switch back to the app — it picks up
automatically once you approve, usually within a few seconds. If nothing
happens after a few minutes, the app will let you try again.

You only do this once — after that, the app remembers you until you log out.

## "This app isn't approved yet"

If you see a message like this instead of a login page, it means the site
hasn't been set up to allow this particular app yet — this isn't something
you can fix yourself. Contact whoever administers the site and let them
know; they'll need to add the app in their settings (see
`admin-auth-guide.md`, §2 if they need the steps).

## Forgot your password?

Click "Lost your password?" on the login page (or browser tab) that opens
when you start logging in — this is WordPress's normal password reset,
handled entirely by the site itself, the same as if you'd gone to log in on
the website directly.

## Advanced: entering a password manually

If the guided login doesn't work for some reason, there's a fallback link
("Advanced: enter an Application Password manually") where you can type in a
username and an *Application Password* directly. This is not your normal
WordPress password — it's a special one generated for connecting apps,
usually already handled for you by the guided flow above. Only use this if
someone (usually your site admin) has specifically given you one to enter.

## Logging out

Logging out doesn't just forget you on this device — it also tells
WordPress to revoke the connection entirely, so if a device is lost or
someone else was using it, logging out is enough; there's nothing further
you need to do on the WordPress site itself. If you want to double check
what's still connected, an admin can see it under WP Admin → Tools → App
Connections.
