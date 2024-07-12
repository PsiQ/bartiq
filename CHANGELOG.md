# Changelog

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
