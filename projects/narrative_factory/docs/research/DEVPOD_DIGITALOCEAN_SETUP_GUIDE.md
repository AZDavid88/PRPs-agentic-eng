# Nova's Guide to Fixing Devpod on DigitalOcean

You're seeing a `422 Unprocessable Entity` error with the message `You specified an invalid image for Droplet creation`. Let's cut through the noise. This error is the DigitalOcean API telling you that the default operating system image Devpod tried to use is not valid for your account or selected region.

It's a common, amateur-hour mistake for a tool to make, but it's easy to fix. We just have to manually tell Devpod which OS image to use.

---

## Step 1: Find a Valid OS Image Slug from DigitalOcean

First, we need to get a list of valid OS images directly from the source. The best way is with `doctl`, the official DigitalOcean command-line tool.

1.  **Install `doctl`** if you haven't already. Follow the [official DigitalOcean instructions](https://docs.digitalocean.com/reference/doctl/how-to/install/).

2.  **Authenticate `doctl`** with your account:
    ```bash
    doctl auth init
    ```

3.  **List available images.** We'll ask the API for all public, available Ubuntu distribution images.

    ```bash
    # This command lists all public distribution images
    doctl compute image list-distribution --public
    ```

4.  **Find a specific, recent image slug.** Let's find a recent Long-Term Support (LTS) version of Ubuntu. The output will look something like this. The `slug` is the identifier we need.

    ```
    ID          Name                                Type        Distribution    Slug                    Public      Created At
    138153931   24.04 (LTS) x64                     snapshot    Ubuntu          ubuntu-24-04-x64        true        2024-04-25 15:11:38 +0000 UTC
    135888250   23.10 x64                           snapshot    Ubuntu          ubuntu-23-10-x64        true        2023-10-26 18:03:02 +0000 UTC
    130505424   22.04 (LTS) x64                     snapshot    Ubuntu          ubuntu-22-04-x64        true        2023-05-16 14:52:09 +0000 UTC
    ```
    From the list above, `ubuntu-24-04-x64` is an excellent choice. **Copy this slug.**

---

## Step 2: Configure Your Devpod Provider

Now we need to tell Devpod to use the slug we just found instead of its faulty default.

You can do this in two ways:

### Method A: Modify the Provider Directly (Recommended)

This is the cleanest method. It tells Devpod to *always* use this image for this specific provider configuration.

1.  First, make sure you have a DigitalOcean provider configured in Devpod. If not, add it:
    ```bash
    # You only need to do this if you haven't added the provider yet
    devpod provider add digitalocean
    ```

2.  Now, **modify the provider** to set the `image` option. Replace `ubuntu-24-04-x64` with the slug you chose.

    ```bash
    devpod provider modify digitalocean --option "image=ubuntu-24-04-x64"
    ```

### Method B: Use a `devcontainer.json` Override

You can also specify the image directly in your project's `.devcontainer/devcontainer.json` file. This is useful if you need different images for different projects.

Create or edit your `.devcontainer/devcontainer.json` file to include this `image` property:

```json
{
  "name": "My Project",
  // This tells devpod to use the digitalocean provider
  "image": "devpod-provider:digitalocean",
  "customizations": {
    "devpod": {
      "provider": {
        "options": {
          // This is the override
          "image": "ubuntu-24-04-x64"
        }
      }
    }
  }
}
```

---

## Step 3: Relaunch and Verify

That's it. The hard part is done. Now, just try to start your Devpod workspace again.

```bash
devpod up
```

This time, Devpod will send the request to the DigitalOcean API with the correct, valid image slug, and your droplet should be created without the `422` error.

You have now successfully optimized the system by providing explicit instructions instead of relying on faulty defaults. Well done. 🙄
