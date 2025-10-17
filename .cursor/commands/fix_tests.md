Review this test. First, look at the code that it tests, analyze its use cases, and think deeply through the common/edge/error cases that the test should cover. Then, look at the test and evaluate:

1. Does it conform to the testing strategy and design as described in @AGENTS.md?
2. Does it properly set up mocks? Did it miss mocking some dependencies and is using real instances? Is it mocking anything that the test doesn't actually need?
3. Do the test functions make sense? Are they well designed? Do they optimally cover the cases that should be tested, or are there gaps, overlaps, or redundancies? Are any test function doing too much or too little?
4. Are there any performance issues, such as overly complex test scaffolding, unnecessary waits or sleeps, etc. that could cause this test to run slowly or consume too many resources?
5. Any other areas where this test can be improved?
6. Run the test. Does it pass?
7. Run `flutter analyze` on just this file. Are there any warnings/errors?

Then, improve this test, rewriting if necessary, so that it fully conforms to the guidelines in @AGENTS.md, and the test functions are well designed, follows best test design practices, are appropriately size, and optimally cover the common/edge/error cases that you identified earlier.

When done, run this test and iterate until everything passes.

When everything passes, evaluate it again using the criteria and questions above. If your answers to all questions are satisfactory, then you are done. If the evaluation identifies any remaining issues, repeat this entire process to fix them.

As a final check, run the test one more time to make sure that it passes, and run `flutter analyze` on it to check for warnings/errors. It MUST be in a fully clean and passing state with no warnings, errors, or failing tests before you complete your task. Finally, run `dart format` on this file.
