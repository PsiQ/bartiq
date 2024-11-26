# Changelog

## [0.8.2](https://github.com/PsiQ/bartiq/compare/v0.8.1...v0.8.2) (2024-11-26)


### Bug Fixes

* Fix defining function in case some of them evaluate to constant ([#144](https://github.com/PsiQ/bartiq/issues/144)) ([dcc5e05](https://github.com/PsiQ/bartiq/commit/dcc5e0523fdbb7d837c23459f0b550313d3ea321))

## [0.8.1](https://github.com/PsiQ/bartiq/compare/v0.8.0...v0.8.1) (2024-11-21)


### Bug Fixes

* add option to allow arbitrary resources for repetitions. ([#140](https://github.com/PsiQ/bartiq/issues/140)) ([3237db1](https://github.com/PsiQ/bartiq/commit/3237db1266a75efd2faac360aae9e623b63f6f72))

## [0.8.0](https://github.com/PsiQ/bartiq/compare/v0.7.0...v0.8.0) (2024-11-07)


### Features

* add repeated structures ([#136](https://github.com/PsiQ/bartiq/issues/136)) ([57312a1](https://github.com/PsiQ/bartiq/commit/57312a13f6de2571f0ce2c51041cca0aff1de485))
* Enable casting to native types and obtaining backend-native functions ([#135](https://github.com/PsiQ/bartiq/issues/135)) ([11628ff](https://github.com/PsiQ/bartiq/commit/11628ff63fce116d6cf018c726f5d6682557ab0f))


### Bug Fixes

* Fix nontrivial input port size support ([#133](https://github.com/PsiQ/bartiq/issues/133)) ([759a367](https://github.com/PsiQ/bartiq/commit/759a367a2b0505e91edcd57ca940e38465b48772))

## [0.7.0](https://github.com/PsiQ/bartiq/compare/v0.6.0...v0.7.0) (2024-10-09)


### Features

* Add Single-Parameter Optimization Module to Bartiq ([#118](https://github.com/PsiQ/bartiq/issues/118)) ([e407474](https://github.com/PsiQ/bartiq/commit/e4074741b41fabf3737fde00d5fcd22138e46652))
* Use ensure_routine to streamline conversion from Qref to Bartiq ([#125](https://github.com/PsiQ/bartiq/issues/125)) ([c03e5f0](https://github.com/PsiQ/bartiq/commit/c03e5f037e01c37e643334ce9a736802d7d6dd2b))


### Bug Fixes

* Fix LaTeX rendering in docs ([#124](https://github.com/PsiQ/bartiq/issues/124)) ([1976ae9](https://github.com/PsiQ/bartiq/commit/1976ae9c0eed9e48a86b8a2e9cd0909b92522ac9))
* handling of function names with "lambda" in them ([#128](https://github.com/PsiQ/bartiq/issues/128)) ([63ad716](https://github.com/PsiQ/bartiq/commit/63ad7169f94b425b01224bc1e34ae0f3b6957275))


### Documentation

* add advanced tutorial to docs ([#129](https://github.com/PsiQ/bartiq/issues/129)) ([2f659a3](https://github.com/PsiQ/bartiq/commit/2f659a3a5772a6d7df0f9bcca16796ec9a763142))

## [0.6.0](https://github.com/PsiQ/bartiq/compare/v0.5.1...v0.6.0) (2024-09-19)


### ⚠ BREAKING CHANGES

* New compilation engine ([#115](https://github.com/PsiQ/bartiq/issues/115))

### Features

* New compilation engine ([#115](https://github.com/PsiQ/bartiq/issues/115)) ([cf79586](https://github.com/PsiQ/bartiq/commit/cf79586354b0ab8dcd708b29bf3caf02cc999ffa))


### Bug Fixes

* Add a parameter to control the removal of decomposed resources in the aggregation function ([#109](https://github.com/PsiQ/bartiq/issues/109)) ([37acec8](https://github.com/PsiQ/bartiq/commit/37acec8f7e7e2f5b338b9b44486ae3f283ec1ee0))


### Documentation

* new tutorial for advanced alias sampling examples and aggregation function ([4a3d789](https://github.com/PsiQ/bartiq/commit/4a3d789b58e6cdce398a81e7ca686c72e0082454))
* Update compilation docs ([#119](https://github.com/PsiQ/bartiq/issues/119)) ([4492a2c](https://github.com/PsiQ/bartiq/commit/4492a2c3cb87cad34be437d7288af871a4697fd5))


### Miscellaneous Chores

* release 0.6.0 ([eefe37a](https://github.com/PsiQ/bartiq/commit/eefe37add4bc47fc51048fe9793e04a32e1dbe3e))

## [0.5.1](https://github.com/PsiQ/bartiq/compare/v0.5.0...v0.5.1) (2024-08-13)


### Bug Fixes

* update alias sampling example ([#103](https://github.com/PsiQ/bartiq/issues/103)) ([0038d3e](https://github.com/PsiQ/bartiq/commit/0038d3efdf429d611feda4d406115d100bb47c2e))

## [0.5.0](https://github.com/PsiQ/bartiq/compare/v0.4.0...v0.5.0) (2024-08-06)


### Features

* add aggregation function for resource decomposition ([#95](https://github.com/PsiQ/bartiq/issues/95)) ([40e2a5b](https://github.com/PsiQ/bartiq/commit/40e2a5b8e4c103b1e04a4379da52a00a99e31ce4))
* add BigO analysis ([#90](https://github.com/PsiQ/bartiq/issues/90)) ([7a24848](https://github.com/PsiQ/bartiq/commit/7a24848995a0a8921c0c155fed9755866b7d43e0))


### Documentation

* correct the cost representation of uniform state preparation in alias sampling tutorials ([7830238](https://github.com/PsiQ/bartiq/commit/78302389bf10a25ed4baa61940711ae653361277))

## [0.4.0](https://github.com/PsiQ/bartiq/compare/v0.3.3...v0.4.0) (2024-07-17)


### Features

* Implement ast-based parser for symbolic expressions ([#87](https://github.com/PsiQ/bartiq/issues/87)) ([c7f642e](https://github.com/PsiQ/bartiq/commit/c7f642e01181945fcdcfcf4d49bdebb3e398801d))
* Improve Value Parsing to Take Mathematical Constants and Functions ([#74](https://github.com/PsiQ/bartiq/issues/74)) ([961dc1c](https://github.com/PsiQ/bartiq/commit/961dc1c853104a384bce3701410940b8558e2937))

## [0.3.3](https://github.com/PsiQ/bartiq/compare/v0.3.2...v0.3.3) (2024-07-12)


### Bug Fixes

* Fix port direction handling in Qref export ([#85](https://github.com/PsiQ/bartiq/issues/85)) ([b6271a3](https://github.com/PsiQ/bartiq/commit/b6271a389cd202a8913efb0c09b9a746e9a43913))

## [0.3.2](https://github.com/PsiQ/bartiq/compare/v0.3.1...v0.3.2) (2024-07-12)


### ⚠ BREAKING CHANGES

* Make local_variables a dictionary instead of a list of strings ([#79](https://github.com/PsiQ/bartiq/issues/79))

### Miscellaneous Chores

* release 0.3.2 ([eb52443](https://github.com/PsiQ/bartiq/commit/eb52443c3e05b4494574dfed9f860dd41b8abd66))


### Code Refactoring

* Make local_variables a dictionary instead of a list of strings ([#79](https://github.com/PsiQ/bartiq/issues/79)) ([2837c2c](https://github.com/PsiQ/bartiq/commit/2837c2c326ddacdcdbf971e560153dc20c5a2d0e))

## [0.3.1](https://github.com/PsiQ/bartiq/compare/v0.3.0...v0.3.1) (2024-07-12)


### Bug Fixes

* correctly passing local variables when converting qref_v1 object to bartiq routine ([295ce32](https://github.com/PsiQ/bartiq/commit/295ce3247b65d36cb19fadf532d99d78d61ea52a))


### Documentation

* add example of qref visualization in tutorials ([c0ee3ea](https://github.com/PsiQ/bartiq/commit/c0ee3eaf5a8bc01e314ae21f0d162f37db7ea273))

## [0.3.0](https://github.com/PsiQ/bartiq/compare/v0.2.0...v0.3.0) (2024-06-25)


### Features

* Custom repr for connection and port ([#54](https://github.com/PsiQ/bartiq/issues/54)) ([ee5b6e7](https://github.com/PsiQ/bartiq/commit/ee5b6e7a0c50d73d4fe4d28d33ffe0f0bcefcb58))
* routine verification ([#76](https://github.com/PsiQ/bartiq/issues/76)) ([cd1940d](https://github.com/PsiQ/bartiq/commit/cd1940d42c881b3eed406efdc1f9d89b6574cbea))
* Streamline parameter linkage ([#65](https://github.com/PsiQ/bartiq/issues/65)) ([8645d90](https://github.com/PsiQ/bartiq/commit/8645d9004c96abaa933f34611aef31daa6c950cd))


### Bug Fixes

* don't add children costs during compilation ([#68](https://github.com/PsiQ/bartiq/issues/68)) ([1ad361f](https://github.com/PsiQ/bartiq/commit/1ad361f0a95172b56d40ab3b0f1cfcbbfa08ac14))
* handling root name ([#69](https://github.com/PsiQ/bartiq/issues/69)) ([ce1f504](https://github.com/PsiQ/bartiq/commit/ce1f5049542b2deb15f26c04ad43212dc40285f8))

## [0.2.0](https://github.com/PsiQ/bartiq/compare/0.1.2...v0.2.0) (2024-06-04)


### Features

* add release pipeline ([#58](https://github.com/PsiQ/bartiq/issues/58)) ([6a2793a](https://github.com/PsiQ/bartiq/commit/6a2793aa8fb33ca20ce84dccc70b762b4d526a1e))
* add routine explorer jupyter widget ([#44](https://github.com/PsiQ/bartiq/issues/44)) ([1dfac28](https://github.com/PsiQ/bartiq/commit/1dfac28820588ab0a18a51c2e8dce71f0267b17b))


### Bug Fixes

* assigning value to evaluated expressions and pruning linked_params ([#52](https://github.com/PsiQ/bartiq/issues/52)) ([0c9c872](https://github.com/PsiQ/bartiq/commit/0c9c872f5e3a8743a58d4e923b7f4b9b88de951f))


### Documentation

* added configuration for GitHub integration ([3879071](https://github.com/PsiQ/bartiq/commit/387907179454e79555f315ae915ce5f6b787ddf2))
* compilation and precompilation docs ([#55](https://github.com/PsiQ/bartiq/issues/55)) ([584e29e](https://github.com/PsiQ/bartiq/commit/584e29ee8834f6759e24d9306ec89aa3b9d3276d))
