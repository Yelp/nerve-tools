# Developing nerve-tools


## Building a testing deb

Manually edit `./src/debian/changelog` and add a new entry/change the version in the top-most entry to a distinct version. Run `make package_bionic` where bionic is the Ubuntu codename you want to test on. Afterwards you'll have a new .deb file in `dist/`.

## Releasing

Edit `./src/setup.py` and change `version` to the version you want to release. Afterwards run `make release`, and run the commands it outputs.

We pin the nerve-tools version in puppet hieradata, so you can roll out new versions per environments/regions

## Testing

Run `make itest_bionic` where bionic is the Ubuntu distribution to test for.
