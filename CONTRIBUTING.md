# How to Contribute

We'd love to accept your patches and contributions to this project. There are
just a few small guidelines you need to follow.

## Contributor License Agreement

Contributions to this project must be accompanied by a Contributor License
Agreement. You (or your employer) retain the copyright to your contribution,
this simply gives us permission to use and redistribute your contributions as
part of the project. Head over to <https://cla.developers.google.com/> to see
your current agreements on file or to sign a new one.

You generally only need to submit a CLA once, so if you've already submitted one
(even if it was for a different project), you probably don't need to do it
again.

## Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more
information on using pull requests.

## Coding style

Use Chromium's Python coding style as described [here][cr-python-style].

You should be able to invoke [YAPF][yapf], which will pick up the style file at
the root of the source tree.

For your convenience, there's a `format_code.sh` script at the root of the
source tree. Once you install YAPF, you can run script before submitting code to
correctly format new code.

## Tests

  * Test files should be named `test_foo` for the `foo` module.

	* When adding doctests, please update the `run_tests.sh` script to include the
		new file.

	* Your tests can use a real `CodeSearch` object and make network requests in
		tests. However, make sure to run `InstallTestRequestHandler` (defined in
		`codesearch/testing_support.py`) in your `setUp()` method so that network
		requests are correctly mocked.

		The first time you run your tests, the tests will fail and complain that
		the requests made by your tests were not cached. This is OK.

		After running and failing the test, run `codesearch/testing_support.py`
		directly from the commandline. The `main` method will analyze the
		placeholder file left by the failed test, fetch the necessary resources from
		the network and write them to `codesearch/testdata/resources`. Your tests
		should now be able to run successfully.

[cr-python-style]: https://chromium.googlesource.com/chromium/src/+/master/styleguide/styleguide.md
[yapf]: https://github.com/google/yapf
