# mozilla-addon-signer
A CLI for signing addon XPIs


### Installation

Clone the repo:
```
$ git clone https://github.com/rehandalal/mozilla-addon-signer.git
```

Install the CLI tool (using a virtualenv is recommended):
```
$ cd mozilla-addon-signer
$ pip install -e .
```

### Getting started

If you manage multiple AWS credentials using named profiles you can 
specify a default profile for the the tool to use by running the 
`configure` command:
```
$ mozilla-addon-signer configure
```

This step is optional and can be skipped. You can also pass the
profile name you wish as an option to the `sign` command.

### Signing an addon

To get a list of available options for the `sign` command use:
```
$ mozilla-addon-signer sign --help
```

You can sign an addon by running:
```
$ mozilla-addon-signer sign path/to/unsigned.xpi
```

If you want the tool to handle downloading the signed addon you may
pass in an addition argument for the destination file path:
```
$ mozilla-addon-signer sign path/to/unsigned.xpi path/to/signed.xpi
```

### Signing an addon from a bugzilla bug

If you want to sign an addon that was attached to a bug in bugzilla
you can pass the bug number to:
```
$ mozilla-addon-signer sign_from_bug 123456
```

If you want the tool to handle downloading the signed addon you may
pass in an addition argument for the destination file path:
```
$ mozilla-addon-signer sign_from_bug 123456 path/to/signed.xpi
```

### Inspecting the certificate of a signed addon

You can view the certificate for a signed addon by running:
```
$ mozilla-addon-signer show_cert path/to/signed.xpi
```
