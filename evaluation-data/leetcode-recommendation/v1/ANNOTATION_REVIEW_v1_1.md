# Reference annotation expansion: v1.1

This is a post-hoc development annotation expansion. It is not held-out ground truth or human approval.

All 4,000 source-owned statements were indexed offline. The frozen plan produced 99 unique topic/problem pairs: 27 already labeled and 72 newly audited. No labels were assigned by rank or random sampling.

Each entry below joins its technical evidence with exact original problem prose. Physical PDF pages are one-based; character offsets are zero-based and end-exclusive. Inherited labels retain their original provenance and are not re-described as independent annotations.

All 72 new pairs passed exact source/identity verification; three semantic relationships remain uncertain. No examples were quarantined for extraction or mapping failure. Automated auditing does not guarantee correctness.

## related-diag-001::lc466 — Count The Repetitions

Topic: Hough transform. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 233; passage [573, 836).

> Let s1 repeat n1 times to form the source. Return the largest m such that s2 repeated n2*m times
> can be selected as a subsequence of that source. Selection may skip source positions but keeps
> their order. Return zero if even one required block cannot be selected.

Technical evidence `related-diag-001-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 504; passage [911, 1326).

> The Hough transform, named after its original inventor (Hough 1962), is a well-known
> technique for having edges “vote” for plausible line locations (Duda and Hart 1972; Ballard
> 1981; Illingworth and Kittler 1988). In its original formulation (Figure 7.46), each edge point
> votes for all possible lines passing through it, and lines corresponding to highaccumulator or
> bin values are examined for potential line ﬁts.

Rationale: The statement asks for subsequence repetition counts in strings, whereas the technical evidence counts votes for geometric lines through image edges.

Limitation: No point coordinates, line incidence, or line-vote accumulator is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-001::lc2152 — Minimum Number of Lines to Cover Points

Topic: Hough transform. Label: **related_practice**.

Collection: bm25_statement rank 3; character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1077; passage [123, 410).

> Input data: an array points where points[i] = [x_i, y_i] identifies a point on an X-Y plane. Straight
> lines are going to be added to the X-Y plane, such that every point is covered by one or more line.
> Required result: the smallest count of straight lines needed to cover all the points.

Technical evidence `related-diag-001-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 504; passage [911, 1326).

> The Hough transform, named after its original inventor (Hough 1962), is a well-known
> technique for having edges “vote” for plausible line locations (Duda and Hart 1972; Ballard
> 1981; Illingworth and Kittler 1988). In its original formulation (Figure 7.46), each edge point
> votes for all possible lines passing through it, and lines corresponding to highaccumulator or
> bin values are examined for potential line ﬁts.

Rationale: Covering planar points with straight lines practices identifying which points can belong to a common line, a geometric component of accumulating line support.

Limitation: The objective minimizes the number of covering lines; it does not specify edge detection, voting, or an accumulator.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-002::lc2373 — Largest Local Values in a Matrix

Topic: Linear filtering. Label: **stretch_connection**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1187; passage [1241, 1585).

> Input data: an n x n integer matrix grid. Generate an integer matrix maxLocal of size (n - 2) x (n -
> 2) such that: maxLocal[i][j] is equal to the largest value of the 3 x 3 matrix in grid centered around
> row i + 1 and column j + 1. we want to find the largest value in every unbroken 3 x 3 matrix in
> grid. Required result: the generated matrix.

Technical evidence `related-diag-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [635, 1003).

> The ﬁlters we have looked at so far have all been linear, i.e., their response to a sum of two
> signals is the same as the sum of the individual responses. This is equivalent to saying that
> each output pixel is a weighted summation of some number of input pixels (3.19). Linear
> ﬁlters are easier to compose and are amenable to frequency response analysis (Section 3.4).

Rationale: Producing an output for each sliding 3-by-3 grid neighborhood practices the neighborhood access needed before combining pixels in a local filter.

Limitation: It computes a maximum rather than a weighted sum; it is not a linear filter.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-002::lc2497 — Maximum Star Sum of a Graph

Topic: Linear filtering. Label: **stretch_connection**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1249; passage [559, 803).

> Given node values vals, undirected edges, and k, choose one center node and at most k of its
> distinct neighbors. The star sum includes the center and chosen neighbors once each. Return the
> largest possible sum; selecting no neighbor is allowed.

Technical evidence `related-diag-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [635, 1003).

> The ﬁlters we have looked at so far have all been linear, i.e., their response to a sum of two
> signals is the same as the sum of the individual responses. This is equivalent to saying that
> each output pixel is a weighted summation of some number of input pixels (3.19). Linear
> ﬁlters are easier to compose and are amenable to frequency response analysis (Section 3.4).

Rationale: Summing a center value and selected adjacent-node values practices the concrete neighborhood-value aggregation component of local filtering.

Limitation: Neighbors are defined by an arbitrary graph and selected to maximize a sum, rather than by a fixed image footprint or kernel.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-002::lc2823 — Deep Object Filter

Topic: Linear filtering. Label: **unrelated**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1412; passage [730, 1293).

> For an object or an array obj and a function fn, compute a filtered object or array filteredObject.
> Function deepFilter should perform a deep filter operation on the obj. The deep filter operation
> should remove properties for which the output of the filter function fn is false, as well as any empty
> objects or arrays that remain after the keys have been removed. If the deep filter operation results
> in an empty object or array, with no remaining properties, deepFilter should produce undefined to
> indicate that there is no valid data left in the filteredObject.

Technical evidence `related-diag-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [635, 1003).

> The ﬁlters we have looked at so far have all been linear, i.e., their response to a sum of two
> signals is the same as the sum of the individual responses. This is equivalent to saying that
> each output pixel is a weighted summation of some number of input pixels (3.19). Linear
> ﬁlters are easier to compose and are amenable to frequency response analysis (Section 3.4).

Rationale: The operation removes nested object properties according to a boolean predicate; the technical operation computes output values by weighted summation.

Limitation: The shared word filter does not establish neighborhood aggregation or linearity.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-002::lc3281 — Maximize Score of Numbers in Ranges

Topic: Linear filtering. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1641; passage [752, 1131).

> Input data: an array of integers start and an integer d, representing n intervals [start[i], start[i] +
> d]. Task: choose n integers with position i integer must belong to the i^th interval. The score of the
> chosen integers means the smallest absolute difference between any two integers that have been
> chosen. Required result: the largest attainable score of the chosen integers.

Technical evidence `related-diag-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [635, 1003).

> The ﬁlters we have looked at so far have all been linear, i.e., their response to a sum of two
> signals is the same as the sum of the individual responses. This is equivalent to saying that
> each output pixel is a weighted summation of some number of input pixels (3.19). Linear
> ﬁlters are easier to compose and are amenable to frequency response analysis (Section 3.4).

Rationale: The task selects integers from intervals to maximize their minimum pairwise separation, rather than aggregating neighboring input values.

Limitation: Neither local grid neighborhoods nor weighted-sum outputs are required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-002::lc3933 — Largest Local Values in a Matrix II

Topic: Linear filtering. Label: **stretch_connection**.

Collection: bm25_statement rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1968; passage [465, 820).

> For every positive-valued cell (r,c), let x=matrix[r][c]. Consider in-grid cells whose absolute row
> and column offsets are both at most x, except cells where both offsets equal x. The cell is a local
> maximum when no considered cell has value greater than x; equal values are allowed. Zero-valued
> cells never qualify. Return the number of qualifying cells.

Technical evidence `related-diag-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [635, 1003).

> The ﬁlters we have looked at so far have all been linear, i.e., their response to a sum of two
> signals is the same as the sum of the individual responses. This is equivalent to saying that
> each output pixel is a weighted summation of some number of input pixels (3.19). Linear
> ﬁlters are easier to compose and are amenable to frequency response analysis (Section 3.4).

Rationale: Inspecting a position-dependent grid neighborhood and comparing its values practices accessing local spatial support around a cell.

Limitation: The output counts local maxima using comparisons; it does not sum weighted inputs and is not linear filtering.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-003::lc308 — Range Sum Query 2D - Mutable

Topic: Summed-area tables. Label: **related_practice**.

Collection: bm25_statement rank 3; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 154; passage [513, 760).

> Design NumMatrix for an integer matrix. update(row, col, val) changes one cell, and
> sumRegion(row1, col1, row2, col2) returns the sum of the inclusive rectangular region between the
> specified corners. Each query must reflect all preceding updates.

Technical evidence `related-diag-003-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [900, 1165).

> If an image is going to be repeatedly convolved with different box ﬁlters (and especially ﬁlters
> of different sizes at different locations), you can precompute the summed area table (Crow
> 1984), which is just the running sum of all the pixel values from the origin,

Technical evidence `related-diag-003-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [1534, 1665).

> To ﬁnd the summed area (integral) inside a rectangle [i0,i 1]× [j0,j 1], we simply
> combine four samples from the summed area table,

Rationale: Repeated rectangular sum queries have the same region-aggregation output as the summed-area-table passage.

Limitation: Cell updates must be reflected in later queries; a static precomputed summed-area table alone does not satisfy that additional requirement. No particular implementation is inferred.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-003::lc935 — Knight Dialer

Topic: Summed-area tables. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 468; passage [94, 375).

> Count length-n digit strings generated by chess-knight moves on the standard telephone keypad,
> starting on any digit. Each step between digits must be a legal knight move; the nondigit corner
> keys cannot be visited. Return the count modulo 1,000,000,007. Initial zeros are allowed.

Technical evidence `related-diag-003-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [900, 1165).

> If an image is going to be repeatedly convolved with different box ﬁlters (and especially ﬁlters
> of different sizes at different locations), you can precompute the summed area table (Crow
> 1984), which is just the running sum of all the pixel values from the origin,

Technical evidence `related-diag-003-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [1534, 1665).

> To ﬁnd the summed area (integral) inside a rectangle [i0,i 1]× [j0,j 1], we simply
> combine four samples from the summed area table,

Rationale: The statement counts digit sequences following knight moves, whereas the evidence precomputes pixel sums for rectangular region queries.

Limitation: A keypad layout does not establish rectangular sum queries or a running-area table.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-003::lc939 — Minimum Area Rectangle

Topic: Summed-area tables. Label: **unrelated**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 470; passage [103, 265).

> Given distinct planar points, return the smallest positive area of an axis-aligned rectangle whose
> four corners are supplied points. Return zero when none exists.

Technical evidence `related-diag-003-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [900, 1165).

> If an image is going to be repeatedly convolved with different box ﬁlters (and especially ﬁlters
> of different sizes at different locations), you can precompute the summed area table (Crow
> 1984), which is just the running sum of all the pixel values from the origin,

Technical evidence `related-diag-003-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [1534, 1665).

> To ﬁnd the summed area (integral) inside a rectangle [i0,i 1]× [j0,j 1], we simply
> combine four samples from the summed area table,

Rationale: This asks for geometric rectangle area from four supplied corner points, rather than a sum of values inside a rectangle.

Limitation: The common word rectangle is insufficient: no image-value aggregation or prefix-area query is specified.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-003::lc963 — Minimum Area Rectangle II

Topic: Summed-area tables. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 482; passage [106, 282).

> Return the smallest positive rectangle area whose four corners are among supplied points.
> Rectangles may rotate; return zero if none exists. Numerical error tolerance is 10^-5.

Technical evidence `related-diag-003-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [900, 1165).

> If an image is going to be repeatedly convolved with different box ﬁlters (and especially ﬁlters
> of different sizes at different locations), you can precompute the summed area table (Crow
> 1984), which is just the running sum of all the pixel values from the origin,

Technical evidence `related-diag-003-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 155; passage [1534, 1665).

> To ﬁnd the summed area (integral) inside a rectangle [i0,i 1]× [j0,j 1], we simply
> combine four samples from the summed area table,

Rationale: The required quantity is the smallest area of a possibly rotated geometric rectangle, not the summed input values in a rectangular region.

Limitation: No pixel array, running sum, or repeated rectangular aggregation is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-004::lc130 — Surrounded Regions

Topic: Connected components. Label: **direct_match**.

Collection: bm25_statement rank 1; character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 65; passage [473, 705).

> A board contains X and O. An O region is connected through horizontal or vertical O neighbors.
> Change every O in a region not connected to a board edge into X, leaving all edge-connected
> regions unchanged. Modify the board in place.

Technical evidence `related-diag-004-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 167; passage [963, 1268).

> Another useful semi-global image operation is ﬁnding connected components, which are de-
> ﬁned as regions of adjacent pixels that have the same input value or label. Pixels are said
> to beN4 adjacent if they are immediately horizontally or vertically adjacent, andN8 if they
> can also be diagonally adjacent.

Rationale: It explicitly identifies horizontally or vertically connected equal-label O regions and distinguishes them by connectivity to the boundary, matching the technical definition of N4 connected regions.

Limitation: Only X/O labels and boundary-enclosed regions are considered; it modifies labels rather than returning every component.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-004::lc1465 — Maximum Area of a Piece of Cake After Horizontal and Vertical Cuts

Topic: Connected components. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 733; passage [444, 1001).

> Input data: a rectangular cake of size h x w and two arrays of integers horizontalCuts and
> verticalCuts where: horizontalCuts[i] is the distance from the top of the rectangular cake to the
> i^th horizontal cut and similarly, and verticalCuts[j] is the distance from the left of the rectangular
> cake to the j^th vertical cut. Required result: the largest area of a piece of cake after you cut at
> each horizontal and vertical position provided in the arrays horizontalCuts and verticalCuts. Since
> the answer can be a large number, produce this modulo 10^9 + 7.

Technical evidence `related-diag-004-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 167; passage [963, 1268).

> Another useful semi-global image operation is ﬁnding connected components, which are de-
> ﬁned as regions of adjacent pixels that have the same input value or label. Pixels are said
> to beN4 adjacent if they are immediately horizontally or vertically adjacent, andN8 if they
> can also be diagonally adjacent.

Rationale: The task maximizes a cake-piece area after supplied horizontal and vertical cuts; connected equal-valued pixels are not part of the operation.

Limitation: Horizontal and vertical directions alone do not establish connected-component labeling.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-004::lc2123 — Minimum Operations to Remove Adjacent Ones in Matrix

Topic: Connected components. Label: **related_practice**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1062; passage [1147, 1475).

> Input data: an indexed-from-zero binary matrix grid. In one operation, you can flip any 1 in grid to
> be 0. A binary matrix is well-isolated if there is no 1 in the matrix that is 4-directionally connected
> (i.e., horizontal and vertical) to another 1. Required result: the smallest count of operations to
> make grid well-isolated.

Technical evidence `related-diag-004-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 167; passage [963, 1268).

> Another useful semi-global image operation is ﬁnding connected components, which are de-
> ﬁned as regions of adjacent pixels that have the same input value or label. Pixels are said
> to beN4 adjacent if they are immediately horizontally or vertically adjacent, andN8 if they
> can also be diagonally adjacent.

Rationale: Determining whether equal-valued one cells are four-directionally adjacent practices the same N4 adjacency relation used to define pixel components.

Limitation: It removes cells until no adjacent ones remain; it does not require enumerating or labeling complete components.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-004::lc2761 — Prime Pairs With Target Sum

Topic: Connected components. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1381; passage [797, 1216).

> Input data: an integer n. Definition: two integers x and y form a prime number pair if: 1 <= x <= y
> <= n x + y == n x and y are prime numbers Required result: the 2D sorted list of prime number
> pairs [x_i, y_i]. The list should be sorted in increasing order of x_i. If there are no prime number
> pairs at all, produce an empty array. A prime number is a natural number greater than 1 with only
> two factors, itself and 1.

Technical evidence `related-diag-004-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 167; passage [963, 1268).

> Another useful semi-global image operation is ﬁnding connected components, which are de-
> ﬁned as regions of adjacent pixels that have the same input value or label. Pixels are said
> to beN4 adjacent if they are immediately horizontally or vertically adjacent, andN8 if they
> can also be diagonally adjacent.

Rationale: The required output is pairs of prime integers with a specified sum, not regions formed by adjacent equal labels.

Limitation: There is no grid adjacency or component relation in the quoted task.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-004::lc3030 — Find the Grid of Region Average

Topic: Connected components. Label: **stretch_connection**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1516; passage [115, 514).

> A valid region is a 3-by-3 subgrid of image in which every horizontally or vertically adjacent pair
> differs in intensity by at most threshold. First compute each valid region's mean intensity, rounded
> down. For each pixel, return the rounded-down mean of those region means over all valid regions
> containing it. A pixel in no valid region retains its original intensity. Return the resulting matrix.

Technical evidence `related-diag-004-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 167; passage [963, 1268).

> Another useful semi-global image operation is ﬁnding connected components, which are de-
> ﬁned as regions of adjacent pixels that have the same input value or label. Pixels are said
> to beN4 adjacent if they are immediately horizontally or vertically adjacent, andN8 if they
> can also be diagonally adjacent.

Rationale: The validity test inspects horizontal and vertical neighbor pairs within an image region, giving concrete practice with the N4 spatial relation.

Limitation: It uses an intensity-difference threshold, fixed 3-by-3 windows and averaging; it does not form maximal connected regions of equal labels.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-005::lc546 — Remove Boxes

Topic: Minimum edit distance. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 273; passage [586, 747).

> Repeatedly remove a consecutive group of k equal boxes to earn k^2 points. Removed neighbors
> close the gap. Return maximum total points after removing every box.

Technical evidence `related-diag-005-t1`: `Speech and Language Processing.pdf`, physical page 68; passage [1746, 1998).

> minimum number of editing operations (operations like insertion, deletion, substitu-
> tion) needed to transform one string into another. In this section we’ll introduce edit
> distance for single words, but the algorithm applies equally to entire strings.

Rationale: The operation scores removal of equal-box groups while closing gaps, rather than finding the fewest character edits between specified source and target strings.

Limitation: Sequence deletion alone does not establish a string-edit transformation task or an edit-distance objective.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-005::lc3335 — Total Characters in String After Transformations I

Topic: Minimum edit distance. Label: **stretch_connection**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1668; passage [611, 1057).

> Input data: a string s and an integer t, representing the count of transformations to perform. In one
> transformation, every character in s is replaced according to these rules: If the character is 'z',
> replace it with the string "ab". Otherwise, replace it with the next character in the alphabet.
> Required result: the length of the resulting string after exactly t transformations. Since the answer
> may be very large, produce it modulo 10^9 + 7.

Technical evidence `related-diag-005-t1`: `Speech and Language Processing.pdf`, physical page 68; passage [1746, 1998).

> minimum number of editing operations (operations like insertion, deletion, substitu-
> tion) needed to transform one string into another. In this section we’ll introduce edit
> distance for single words, but the algorithm applies equally to entire strings.

Rationale: Applying specified character replacements to a string practices a concrete rewriting operation related to the substitution primitive in edit distance.

Limitation: The replacements are prescribed and applied for a fixed number of rounds; the task returns a length and does not minimize edits to a target string.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-005::lc3337 — Total Characters in String After Transformations II

Topic: Minimum edit distance. Label: **stretch_connection**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1669; passage [701, 1230).

> Input data: a string s containing English letters a-z, an integer t representing the count of
> transformations to perform, and an array nums of size 26. In one transformation, every character
> in s is replaced according to these rules: Replace s[i] with the next nums[s[i] - 'a'] successive
> characters in the alphabet. The transformation wraps around the alphabet if it exceeds 'z'.
> Required result: the length of the resulting string after exactly t transformations. Since the answer
> may be very large, produce it modulo 10^9 + 7.

Technical evidence `related-diag-005-t1`: `Speech and Language Processing.pdf`, physical page 68; passage [1746, 1998).

> minimum number of editing operations (operations like insertion, deletion, substitu-
> tion) needed to transform one string into another. In this section we’ll introduce edit
> distance for single words, but the algorithm applies equally to entire strings.

Rationale: Replacing input characters with specified character sequences gives limited practice in constructing a transformed string through character-level rewrite rules.

Limitation: The task computes length after fixed transformations, not insertion/deletion/substitution costs or minimum distance between two strings.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-005::lc3675 — Minimum Operations to Transform String

Topic: Minimum edit distance. Label: **related_practice**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1839; passage [621, 1062).

> Input data: a string s consisting only of English letters a-z. Permitted: perform this operation zero
> or more times (including zero): Choose any character c in the string and replace every occurrence
> of c with the next lowercase letter in the English alphabet. Required result: the smallest count of
> operations required to transform s into a string containing only 'a' characters. Consider the
> alphabet as circular, thus 'a' comes after 'z'.

Technical evidence `related-diag-005-t1`: `Speech and Language Processing.pdf`, physical page 68; passage [1746, 1998).

> minimum number of editing operations (operations like insertion, deletion, substitu-
> tion) needed to transform one string into another. In this section we’ll introduce edit
> distance for single words, but the algorithm applies equally to entire strings.

Rationale: It minimizes character-replacement operations needed to transform a string into a specified all-a form, sharing the minimum-cost string-transformation task.

Limitation: One operation changes every occurrence of a chosen letter to its alphabetic successor; this differs from single-position edits and does not permit arbitrary insertions or deletions.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-006::lc1961 — Check If String Is a Prefix of Array

Topic: Trie prefix lookup. Label: **stretch_connection**.

Collection: bm25_statement rank 3; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 981; passage [941, 1230).

> For a string s and an array of strings words, compute whether s is a prefix string of words. A string
> s is a prefix string of words if s can be made by concatenating the first k strings in words for some
> positive k no larger than words.length. Decide whether s is a prefix string of words.

Technical evidence `related-diag-006-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 93; passage [6, 242).

> One of the most appropriate data structures that can serve our purpose is the Trie 
> (pronounced “try”). A trie is a tree-like data structure used to store phrases where 
> each node stores a character of the phrase in a sequential manner.

Technical evidence `related-diag-006-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 93; passage [369, 540).

> Now if the user has typed ‘cap’, our service can traverse the trie to go to the node ‘P’ 
> to find all the terms that start with this prefix (e.g., cap-tion, cap-ital etc).

Technical evidence `related-diag-006-extra-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 94; passage [1248, 1542).

> How would we build this trie? We can efficiently build our trie bottom up. Each 
> parent node will recursively call all the child nodes to calculate their top suggestions 
> and their counts. Parent nodes will combine top suggestions from all of their 
> children to determine their top suggestions.

Rationale: Testing whether a supplied string is an initial character sequence of a concatenation practices the prefix comparison underlying prefix lookup.

Limitation: There is no stored dictionary, character-node tree, or requirement to return all phrases sharing a prefix.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-006::lc3372 — Maximize the Number of Target Nodes After Connecting Trees I

Topic: Trie prefix lookup. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1687; passage [144, 1118).

> There exist two undirected trees with n and m nodes, with different labels in ranges [0, n - 1] and
> [0, m - 1], respectively. Input data: two 2D integer arrays edges1 and edges2 of lengths n - 1 and
> m - 1, respectively, where edges1[i] = [a_i, b_i] specifies that there is an edge between nodes a_i
> and b_i in the first tree and edges2[i] = [u_i, v_i] specifies that there is an edge between nodes u_i
> and v_i in the second tree. Input data: an integer k. Node u is target to node v if the count of edges
> on the path from u to v is less than or equal to k. Note that a node is always target to itself.
> Required result: an array of n integers answer, where answer[i] is the largest attainable number of
> nodes target to node i of the first tree if you have to connect one node from the first tree to
> another node in the second tree. Note that queries are independent from each other. That is, for
> every query you will remove the added edge before proceeding to the next query.

Technical evidence `related-diag-006-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 93; passage [6, 242).

> One of the most appropriate data structures that can serve our purpose is the Trie 
> (pronounced “try”). A trie is a tree-like data structure used to store phrases where 
> each node stores a character of the phrase in a sequential manner.

Technical evidence `related-diag-006-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 93; passage [369, 540).

> Now if the user has typed ‘cap’, our service can traverse the trie to go to the node ‘P’ 
> to find all the terms that start with this prefix (e.g., cap-tion, cap-ital etc).

Technical evidence `related-diag-006-extra-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 94; passage [1248, 1542).

> How would we build this trie? We can efficiently build our trie bottom up. Each 
> parent node will recursively call all the child nodes to calculate their top suggestions 
> and their counts. Parent nodes will combine top suggestions from all of their 
> children to determine their top suggestions.

Rationale: The statement optimizes counts of nodes within a distance after connecting undirected trees; the technical task stores and searches character prefixes.

Limitation: The common tree terminology does not establish shared string-prefix operations.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-007::lc1756 — Design Most Recently Used Queue

Topic: LRU eviction. Label: **related_practice**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 879; passage [115, 409).

> Design a queue-like data structure that moves the most recently used element to the end of the
> queue. Build MRUQueue class: MRUQueue(int n) constructs the MRUQueue with n elements:
> [1,2,3,...,n]. int fetch(int k) moves the k^th element (indexed from one) to the end of the queue
> and returns it.

Technical evidence `related-diag-007-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 24; passage [100, 552).

> Which cache eviction policy would best fit our needs? When the cache is full, 
> and we want to replace a link with a newer/hotter URL, how would we choose? Least 
> Recently Used (LRU) can be a reasonable policy for our system. Under this policy, 
> we discard the least recently used URL first. We can use a Linked Hash Map or a 
> similar data structure to store our URLs and Hashes, which will also keep track of 
> the URLs that have been accessed recently.

Rationale: Moving a fetched element to the end explicitly maintains access-recency order, a concrete component needed to distinguish least-recently-used entries.

Limitation: The queue fetches by rank and never evicts an entry or implements key-value cache operations.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-007::lc1994 — The Number of Good Subsets

Topic: LRU eviction. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 998; passage [108, 717).

> Input data: an array of integers nums. We call a subset of nums good if its product can be
> represented as a product of one or more different prime numbers. [2, 3], [1, 2, 3], and [1, 3] are
> good subsets with products 6 = 2*3, 6 = 2*3, and 3 = 3 respectively. [1, 4] and [4] are not good
> subsets with products 4 = 2*2 and 4 = 2*2 respectively. Required result: the count of different
> good subsets in nums modulo 10^9 + 7. A subset of nums is any array that can result by deleting
> some (possibly none or all) elements from nums. Two subsets are different exactly when the
> chosen indices to delete are different.

Technical evidence `related-diag-007-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 24; passage [100, 552).

> Which cache eviction policy would best fit our needs? When the cache is full, 
> and we want to replace a link with a newer/hotter URL, how would we choose? Least 
> Recently Used (LRU) can be a reasonable policy for our system. Under this policy, 
> we discard the least recently used URL first. We can use a Linked Hash Map or a 
> similar data structure to store our URLs and Hashes, which will also keep track of 
> the URLs that have been accessed recently.

Rationale: It counts subsets whose products contain distinct prime factors, rather than maintaining cache access order or evicting old entries.

Limitation: No recency state or cache-capacity operation is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-007::lc2933 — High-Access Employees

Topic: LRU eviction. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1467; passage [688, 1464).

> Input data: a 2D indexed from zero array of strings, access_times, with size n. For each i where 0
> <= i <= n - 1, access_times[i][0] identifies the name of an employee, and access_times[i][1]
> identifies the access time of that employee. All entries in access_times are within the same day.
> The access time is represented as four digits using a 24-hour time format, An employee qualifies
> as high-access if he has accessed the system three or more times within a one-hour period. Times
> with exactly one hour of difference are not considered part of the same one-hour period. Access
> times at the start and end of the day are not counted within the same one-hour period. Required
> result: a list that contains the names of high-access employees with an unrestricted order you
> want.

Technical evidence `related-diag-007-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 24; passage [100, 552).

> Which cache eviction policy would best fit our needs? When the cache is full, 
> and we want to replace a link with a newer/hotter URL, how would we choose? Least 
> Recently Used (LRU) can be a reasonable policy for our system. Under this policy, 
> we discard the least recently used URL first. We can use a Linked Hash Map or a 
> similar data structure to store our URLs and Hashes, which will also keep track of 
> the URLs that have been accessed recently.

Rationale: The statement counts employee accesses within a fixed time window; the technical passage maintains recency order to choose one cache entry for eviction.

Limitation: Access records alone do not require least-recently-used ordering or capacity-triggered replacement.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc863 — All Nodes Distance K in Binary Tree

Topic: Topological ordering. Label: **unrelated**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 432; passage [116, 271).

> Given a binary tree and a target node, return values of nodes exactly k edges away, allowing
> movement to parents or children. Output order is unrestricted.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: The task returns nodes at a fixed distance with unrestricted output order, whereas the evidence requires parents to precede children in a DAG ordering.

Limitation: Parent-child references alone do not require a dependency-respecting order.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc1557 — Minimum Number of Vertices to Reach All Nodes

Topic: Topological ordering. Label: **uncertain**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 779; passage [306, 682).

> With a directed acyclic graph, with n vertices numbered from 0 to n-1, and an array edges where
> edges[i] = [from_i, to_i] identifies a directed edge from node from_i to node to_i. Find the smallest
> set of vertices from which all nodes in the graph are reachable. It's guaranteed that a unique
> solution exists. Notice that you can produce the vertices in an unrestricted order.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: Both passages concern a DAG, and a reachability task could use structural information also relevant to dependency ordering.

Limitation: The statement asks for a minimum reaching set with unrestricted output order and does not require parent-before-child processing. Inferring a useful common ordering operation would assume an unstated solution.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc1659 — Maximize Grid Happiness

Topic: Topological ordering. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 830; passage [612, 1490).

> Input data: four integers, m, n, introvertsCount, and extrovertsCount. Available: an m x n grid, and
> there are two types of people: introverts and extroverts. The setting contains introvertsCount
> introverts and extrovertsCount extroverts. You should decide how many people you want to live in
> the grid and assign each of them one grid cell. Note that you do not have to have all the people
> living in the grid. The happiness of each person is calculated as follows: Introverts start with 120
> happiness and lose 30 happiness for each neighbor (introvert or extrovert). Extroverts start with
> 40 happiness and gain 20 happiness for each neighbor (introvert or extrovert). Neighbors live in
> the directly adjacent cells north, east, south, and west of a person's cell. The grid happiness is the
> total of each person's happiness. Required result: the largest attainable grid happiness.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: This assigns people to grid cells to maximize a neighborhood happiness sum, rather than ordering directed dependencies.

Limitation: No DAG or parent-before-child requirement appears in the task.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc2204 — Distance to a Cycle in Undirected Graph

Topic: Topological ordering. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1103; passage [121, 755).

> Input data: an integer greater than zero n representing the count of nodes in a connected
> undirected graph containing exactly one cycle. The nodes are numbered from 0 to n - 1 (inclusive).
> Input data: a two-dimensional array of integers edges, where edges[i] = [node1_i, node2_i]
> specifies that there is a bidirectional edge connecting node1_i and node2_i in the graph. The
> distance between two nodes a and b is defined to be the smallest count of edges that are needed
> to go from a to b. Required result: an array of integers answer of size n, where answer[i] is the
> smallest distance between the i^th node and any node in the cycle.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: It computes distance to a cycle in an undirected graph, while the technical operation orders nodes of an acyclic directed graph.

Limitation: Graph terminology does not establish the required direction, acyclicity, or dependency order.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc2316 — Count Unreachable Pairs of Nodes in an Undirected Graph

Topic: Topological ordering. Label: **unrelated**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1159; passage [139, 485).

> Input data: an integer n. There is an undirected graph with n nodes, numbered from 0 to n - 1.
> Input data: a two-dimensional array of integers edges where edges[i] = [a_i, b_i] specifies that
> there exists an undirected edge connecting nodes a_i and b_i. Required result: the count of pairs of
> different nodes that are unreachable from each other.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: Counting unreachable pairs in an undirected graph does not specify ordering nodes so that every parent precedes its children.

Limitation: The statement supplies no directed precedence relation or order-construction task.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-008::lc2876 — Count Visited Nodes in a Directed Graph

Topic: Topological ordering. Label: **unrelated**.

Collection: bm25_statement rank 1; character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1439; passage [121, 690).

> The setting contains a directed graph containing n nodes numbered from 0 to n - 1 and n directed
> edges. Input data: an indexed-from-zero array edges where edges[i] specifies that there is an edge
> from node i to node edges[i]. Consider the following process on the graph: You start from a node x
> and keep visiting other nodes through edges until you reach a node that you have already visited
> before on this same process. Required result: an array answer where answer[i] is the count of
> different nodes that you will visit if you perform the process beginning at node i.

Technical evidence `related-diag-008-t1`: `Probabilistic Machine Learning.pdf`, physical page 177; passage [1940, 2076).

> The key property of a DAG is that the nodes can be ordered such that parents come before children.
> This is called atopological ordering.

Rationale: The required process follows directed edges until revisiting a node and counts visits, rather than producing an order of an acyclic dependency graph.

Limitation: Directed edges alone are insufficient: the walk explicitly permits cyclic revisits and does not require topological ordering.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc109 — Convert Sorted List to Binary Search Tree

Topic: Binary search on sorted records. Label: **uncertain**.

Collection: bm25_statement rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 55; passage [122, 279).

> Convert a sorted singly linked list into a binary search tree retaining every value. Each node's
> subtree heights must differ by at most one. Return its root.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: The input is sorted and the output is a binary search tree, so ordered-data organization may be useful practice for sorted-key lookup.

Limitation: The task is balanced-tree construction, not searching for a key; any divide-and-search implementation or direct lookup benefit would be an additional interpretation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc700 — Search in a Binary Search Tree

Topic: Binary search on sorted records. Label: **related_practice**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 350; passage [563, 671).

> Find val in a binary search tree and return the root of that node's subtree. Return null when val is
> absent.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: Finding a given key in a binary search tree practices ordered-key lookup, the purpose served by binary search over a sorted segment.

Limitation: The storage is a linked search tree rather than a sorted segment file or array; the source does not establish identical access costs or layout assumptions.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc1373 — Maximum Sum BST in Binary Tree

Topic: Binary search on sorted records. Label: **unrelated**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 687; passage [833, 1215).

> For a binary tree root, compute the largest sum of all keys of any sub-tree which is also a Binary
> Search Tree (BST). Assume a BST means follows: The left subtree of a node contains only nodes
> with keys less than the node's key. The right subtree of a node contains only nodes with keys
> greater than the node's key. Both the left and right subtrees must also be binary search trees.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: The task identifies a maximum-sum subtree satisfying BST ordering constraints; it does not ask to locate a target record by exploiting sorted order.

Limitation: Ordered-key constraints alone do not establish the sorted-record search operation in the technical passage.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc1382 — Balance a Binary Search Tree

Topic: Binary search on sorted records. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 692; passage [112, 379).

> For the root of a binary search tree, compute a balanced binary search tree with the same node
> values. If there is more than one answer, produce any of them. A binary search tree is balanced if
> the depth of the two subtrees of every node never differs by more than 1.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: It restructures a search tree to balance subtree depths, rather than looking up a value in sorted records.

Limitation: The shared binary-search-tree name does not require the technical key-lookup operation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc1902 — Depth of BST Given Insertion Order

Topic: Binary search on sorted records. Label: **uncertain**.

Collection: bm25_statement rank 3; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 952; passage [118, 948).

> Input data: an indexed-from-zero integer array order of length n, a permutation of integers from 1
> to n representing the order of insertion into a binary search tree. A binary search tree means
> follows: The left subtree of a node contains only nodes with keys less than the node's key. The
> right subtree of a node contains only nodes with keys greater than the node's key. Both the left
> and right subtrees must also be binary search trees. The binary search tree is constructed as
> follows: order[0] is the root of the binary search tree. All subsequent elements are inserted as the
> child of any existing node such that the binary search tree properties hold. Required result: the
> depth of the binary search tree. A binary tree's depth is the count of nodes along the longest path
> from the root node down to the farthest leaf node.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: Inserting keys while maintaining smaller-left and larger-right constraints may exercise ordered placement related to finding a key's sorted interval.

Limitation: The required result is tree depth, not a key-search result. A specific binary-search-based insertion method is not stated and should not be assumed.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-009::lc2225 — Find Players With Zero or One Losses

Topic: Binary search on sorted records. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1113; passage [733, 1288).

> Input data: an array of integers matches where matches[i] = [winner_i, loser_i] specifies that the
> player winner_i defeated player loser_i in a match. Required result: a list answer of size 2 where:
> answer[0] is a list of all players that have not lost any matches. answer[1] is a list of all players
> that have lost exactly one match. The values in the two lists should be returned in increasing
> order. You should only consider the players that have played one or more match. The testcases is
> generated such that no two matches will have the same outcome.

Technical evidence `related-diag-009-t1`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [3, 292).

> If all keys and values had a fixed size, you could use binary search on a segment file and avoid the in-
> memory index entirely. However, they are usually variable-length in practice, which makes it difficult to tell
> where one record ends and the next one starts if you don’t have an index.

Technical evidence `related-diag-009-t2`: `Designing Data-Intensive Applications.pdf`, physical page 99; passage [1081, 1158).

> because of the sorting you know that handiwork must appear between those two.

Rationale: The statement classifies players by loss counts and sorts the output; it does not search for a target within an existing sorted record collection.

Limitation: Sorting a result is insufficient evidence for a binary-search lookup connection.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-010::lc208 — Implement Trie (Prefix Tree)

Topic: Bloom filter membership. Label: **related_practice**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 104; passage [569, 869).

> Design Trie with insert(word), search(word), and startsWith(prefix). search reports whether the
> exact word was inserted; startsWith reports whether some inserted word has that initial character
> sequence. Maintain all inserted words across calls, with duplicate insertion leaving membership
> unchanged.

Technical evidence `related-diag-010-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 126; passage [1293, 1760).

> Bloom filters are a probabilistic data 
> structure for set membership testing that may yield false positives. A large bit vector 
> represents the set. An element is added to the set by computing ‘n’ hash functions of 
> the element and setting the corresponding bits. An element is deemed to be in the 
> set if the bits at all ‘n’ of the element’s hash locations are set. Hence, a document 
> may incorrectly be deemed to be in the set, but false negatives are not possible.

Rationale: The insert and exact search operations maintain set membership across calls, sharing the membership-testing interface that a Bloom filter approximates.

Limitation: A trie stores exact string membership and supports prefixes; the statement does not require hash locations, a bit vector, or probabilistic false positives.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-010::lc368 — Largest Divisible Subset

Topic: Bloom filter membership. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 184; passage [286, 423).

> Return a largest subset of distinct positive nums such that for every pair, one divides the other.
> Any maximum-size subset is acceptable.

Technical evidence `related-diag-010-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 126; passage [1293, 1760).

> Bloom filters are a probabilistic data 
> structure for set membership testing that may yield false positives. A large bit vector 
> represents the set. An element is added to the set by computing ‘n’ hash functions of 
> the element and setting the corresponding bits. An element is deemed to be in the 
> set if the bits at all ‘n’ of the element’s hash locations are set. Hence, a document 
> may incorrectly be deemed to be in the set, but false negatives are not possible.

Rationale: The task maximizes a subset satisfying pairwise divisibility, rather than implementing insertions and membership queries.

Limitation: The word subset does not establish the set-membership data-structure operation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-010::lc1318 — Minimum Flips to Make a OR b Equal to c

Topic: Bloom filter membership. Label: **stretch_connection**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 659; passage [562, 826).

> With 3 positives numbers a, b and c. Required result: the smallest flips required in some bits of a
> and b to make ( a OR b == c ). (bitwise OR operation). Flip operation contains change any single
> bit 1 to 0 or change the bit 0 to 1 in their binary representation.

Technical evidence `related-diag-010-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 126; passage [1293, 1760).

> Bloom filters are a probabilistic data 
> structure for set membership testing that may yield false positives. A large bit vector 
> represents the set. An element is added to the set by computing ‘n’ hash functions of 
> the element and setting the corresponding bits. An element is deemed to be in the 
> set if the bits at all ‘n’ of the element’s hash locations are set. Hence, a document 
> may incorrectly be deemed to be in the set, but false negatives are not possible.

Rationale: Changing individual bits to satisfy a bitwise OR condition gives limited practice with explicit bit-state updates and tests, a primitive used when manipulating Bloom-filter bits.

Limitation: It is an integer bit-edit optimization task, not membership testing; no hash functions, element insertions, or false-positive behavior are specified.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-010::lc1570 — Dot Product of Two Sparse Vectors

Topic: Bloom filter membership. Label: **unrelated**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 786; passage [117, 558).

> With two sparse vectors, compute their dot product. Implement class SparseVector:
> SparseVector(nums) Initializes the object with the vector nums dotProduct(vec) Compute the dot
> product between the instance of SparseVector and vec A sparse vector is a vector that has mostly
> zero values, you should store the sparse vector efficiently and compute the dot product between
> two SparseVector. Follow up: What if only one of the vectors is sparse?

Technical evidence `related-diag-010-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 126; passage [1293, 1760).

> Bloom filters are a probabilistic data 
> structure for set membership testing that may yield false positives. A large bit vector 
> represents the set. An element is added to the set by computing ‘n’ hash functions of 
> the element and setting the corresponding bits. An element is deemed to be in the 
> set if the bits at all ‘n’ of the element’s hash locations are set. Hence, a document 
> may incorrectly be deemed to be in the set, but false negatives are not possible.

Rationale: The statement computes a sparse-vector dot product, while the technical evidence inserts elements and tests their hash-derived bit positions.

Limitation: A hash-based sparse implementation is not required by the statement and cannot be assumed as a shared membership operation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc36 — Valid Sudoku

Topic: Consistent-hash ring lookup. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 18; passage [516, 878).

> A 9-by-9 Sudoku board contains digit characters 1 through 9 and periods marking empty cells.
> Return whether its current filled cells obey Sudoku rules: no repeated digit within any row, column,
> or one of the nine fixed 3-by-3 boxes. Ignore empty cells. You are checking the present
> arrangement only; a board need not admit a complete solution to pass this check.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: The task checks repeated Sudoku digits in rows, columns and boxes; the technical mechanism routes a hashed position to the next cache on a circular order.

Limitation: No ring, clockwise traversal, or successor-cache query is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc285 — Inorder Successor in BST

Topic: Consistent-hash ring lookup. Label: **related_practice**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 143; passage [105, 288).

> Given a binary search tree root and a node p in it, return p's inorder successor: the node with the
> smallest value strictly greater than p's value. Return null if no successor exists.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: Finding the smallest stored value greater than a position practices successor lookup, the ordered-selection component of choosing the next cache clockwise.

Limitation: The BST successor is strict and returns null at the end; a hash ring wraps around and also includes hashing and cache assignment.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc460 — LFU Cache

Topic: Consistent-hash ring lookup. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 230; passage [350, 697).

> Design LFUCache(capacity) with get(key) and put(key, value). A missing get returns -1. Successful
> reads and updates increase that key's usage count; new keys start at one. When insertion exceeds
> capacity, evict the least-used key, breaking ties by least recent use. Reads and writes require O(1)
> average time. A zero-capacity cache stores nothing.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: The statement evicts entries from one cache according to frequency and recency; the technical mechanism assigns a key to a cache by its ring position.

Limitation: The common cache vocabulary does not establish circular successor lookup or distributed key placement.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc510 — Inorder Successor in BST II

Topic: Consistent-hash ring lookup. Label: **related_practice**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 255; passage [277, 506).

> Given a node in a binary search tree whose nodes have parent pointers, return its inorder
> successor, or null if absent. The successor has the smallest value larger than the given node. You
> are given the node itself, not the root.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: Selecting the smallest value larger than a given node practices the same ordered-successor component used after mapping a key onto a cache ring.

Limitation: It uses parent pointers, has no wraparound, and does not hash keys or select among distributed caches.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc2103 — Rings and Rods

Topic: Consistent-hash ring lookup. Label: **unrelated**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1052; passage [1538, 2140).

> The setting contains n rings and each ring is either red, green, or blue. The rings are distributed
> across ten rods labeled from 0 to 9. Input data: a string rings of length 2n that describes the n
> rings that are placed onto the rods. Every two characters in rings forms a color-position pair that is
> used to describe each ring where: The first character of the i^th pair specifies the i^th ring's color
> ('R', 'G', 'B'). The second character of the i^th pair specifies the rod that the i^th ring is placed on
> ('0' to '9'). Required result: the count of rods that have all three colors of rings on them.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: The statement counts rods bearing three colors of physical rings, whereas the technical ring is a circular ordering of hash positions.

Limitation: The shared word ring describes different data and operations; no clockwise position lookup is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-011::lc2682 — Find the Losers of the Circular Game

Topic: Consistent-hash ring lookup. Label: **stretch_connection**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1342; passage [118, 420).

> Friends labeled 1 through n sit clockwise. Friend 1 initially receives a ball. On pass i=1,2,..., the
> holder passes it i*k positions clockwise, wrapping around. Stop immediately when a friend receives
> the ball for a second time. Return, in increasing order, the labels of friends who never received it.

Technical evidence `related-diag-011-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 190; passage [1799, 2043).

> As a typical hash function, consistent hashing maps a key to an integer. Suppose the 
> output of the hash function is in the range of [0, 256). Imagine that the integers in 
> the range are placed on a ring such that the values are wrapped around.

Technical evidence `related-diag-011-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 191; passage [7, 160).

> o Hash it to a single integer. 
> o Move clockwise on the ring until finding the first cache it encounters. 
> o That cache is the one that contains the key.

Rationale: Moving clockwise by a position count with wraparound practices circular-coordinate handling, one component of traversing a hash ring.

Limitation: It simulates ball passes and repeated recipients rather than locating the first cache at or after a hashed key position.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc856 — Score of Parentheses

Topic: Beam-search frontier pruning. Label: **unrelated**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 428; passage [516, 700).

> Score a balanced parentheses string: an empty sequence scores zero, a pair scores one,
> concatenation adds scores, and enclosing a nonempty sequence doubles its score. Return the
> total.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: It evaluates a fixed parentheses string by arithmetic composition; beam search expands candidate continuations and keeps a bounded best-scoring frontier.

Limitation: A score alone does not establish branching hypotheses or top-k pruning.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc946 — Validate Stack Sequences

Topic: Beam-search frontier pruning. Label: **unrelated**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 473; passage [374, 523).

> Given distinct pushed and popped sequences, return whether a stack can push in the first order
> and pop in the second. Pushes and pops may interleave.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: The task checks whether two fixed sequences are consistent with stack operations, rather than extending and scoring candidate hypotheses.

Limitation: Sequence terminology does not establish best-k frontier selection.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc2242 — Maximum Score of a Node Sequence

Topic: Beam-search frontier pruning. Label: **related_practice**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1122; passage [114, 842).

> There is an undirected graph with n nodes, numbered from 0 to n - 1. Input data: an
> indexed-from-zero integer array scores of length n where scores[i] specifies the score of node i.
> Input data: a two-dimensional array of integers edges where edges[i] = [a_i, b_i] specifies that
> there exists an undirected edge connecting nodes a_i and b_i. A node sequence is valid if it meets
> these requirements: There is an edge connecting every pair of adjacent nodes in the sequence. No
> node appears more than once in the sequence. The score of a node sequence means the total of
> the scores of the nodes in the sequence. Required result: the largest score of a valid node
> sequence with a length of 4. If no such sequence exists, produce -1.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: Choosing a maximum-scoring valid node sequence practices scoring and comparing alternative connected sequences, a concrete component of scoring search hypotheses.

Limitation: The score is an additive node sum for a fixed four-node path; the statement does not prescribe probability products, a bounded frontier, or beam pruning.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc3051 — Find Candidates for Data Scientist Position

Topic: Beam-search frontier pruning. Label: **unrelated**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1526; passage [1106, 1362).

> Write a query
> to find the candidates best suited for a Data Scientist position. The candidate must be proficient in
> Python, Tableau, and PostgreSQL. Required result: the result table ordered by candidate_id in
> ascending order. Output columns: candidate_id.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: The task filters applicants by three required skills; the technical passage extends token hypotheses and prunes them by sequence probability.

Limitation: The word candidates does not imply sequence generation or best-k search. The label relies only on the quoted prose task, not on interpreting the schema table.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc3320 — Count The Number of Winning Sequences

Topic: Beam-search frontier pruning. Label: **stretch_connection**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1661; passage [119, 454).

> Alice's sequence s uses F,W,E. Each round awards one point to the winner according to F beating
> E, W beating F, and E beating W; equal choices award neither player a point. Bob may choose any
> sequence of the same length with no equal consecutive choices. Count Bob's sequences whose
> final score strictly exceeds Alice's, modulo 10^9+7.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: Constructing constrained alternative sequences and comparing their accumulated game scores gives limited practice with scored sequence continuations.

Limitation: The objective counts all winning sequences rather than retaining the best k; game scores are not token probabilities and no pruning policy is specified.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-diag-012::lc3415 — Find Products with Three Consecutive Digits

Topic: Beam-search frontier pruning. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1709; passage [1139, 1433).

> Find all products whose names contain a sequence of
> exactly three successive digits in a row. Required result: the result table ordered by product_id in
> ascending order. Note that the name may contain multiple such sequences, but each should have
> length three. Output columns: product_id, name.

Technical evidence `related-diag-012-t1`: `Speech and Language Processing.pdf`, physical page 295; passage [2179, 2735).

> At subsequent steps, each of thekbest hypotheses is extended incrementally
> by being passed to distinct decoders, which each generate a softmax over the entire
> vocabulary to extend the hypothesis to every possible next token. Each of thesek×V
> hypotheses is scored byP(y i|x,y<i): the product of the probability of the current
> word choice multiplied by the probability of the path that led to it. We then prune
> thek×Vhypotheses down to thekbest hypotheses, so there are never more thank
> hypotheses at the frontier of the search, and never more thankdecoders.

Rationale: The task finds a fixed digit pattern in product names; it does not score, extend or retain competing sequence hypotheses.

Limitation: Sequence wording alone is insufficient. The label uses only the prose search condition and does not depend on a schema table.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-001::lc239 — Sliding Window Maximum

Topic: Median neighborhood filtering. Label: **related_practice**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 120; passage [101, 223).

> For every length-k contiguous window of nums, return its largest value. Order results by increasing
> window starting index.

Technical evidence `related-fresh-001-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [1454, 1586).

> A better ﬁlter to use in this case is themedian ﬁlter, which selects the median value from each
> pixel’s neighborhood (Figure 3.19a).

Rationale: Computing a statistic for every contiguous neighborhood practices sliding-neighborhood access and local order-statistic output, as required before selecting a median.

Limitation: The statistic is a maximum rather than a median, and neighborhoods are one-dimensional windows instead of image neighborhoods.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-001::lc1643 — Kth Smallest Instructions

Topic: Median neighborhood filtering. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 822; passage [960, 1695).

> Bob is standing at cell (0, 0), and he wants to reach destination: (row, column). He can only travel
> right and down. You are going to help Bob by providing instructions for him to reach destination.
> The instructions are represented as a string, with each character is either: 'H', meaning move
> horizontally (go right), or 'V', meaning move vertically (go down). Multiple instructions will lead Bob
> to destination. However, Bob is very picky. Bob has a lucky number k, and he wants the k^th
> lexicographically smallest instructions that will lead him to destination. k is indexed from one. With
> an array of integers destination and an integer k, produce the k^th lexicographically smallest
> instructions that will take Bob to destination.

Technical evidence `related-fresh-001-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [1454, 1586).

> A better ﬁlter to use in this case is themedian ﬁlter, which selects the median value from each
> pixel’s neighborhood (Figure 3.19a).

Rationale: It selects the kth lexicographic movement-instruction string among paths, while the technical operation selects a median of neighboring pixel values.

Limitation: A rank parameter and grid coordinates do not establish a local neighborhood statistic.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-001::lc3555 — Smallest Subarray to Sort in Every Sliding Window

Topic: Median neighborhood filtering. Label: **stretch_connection**.

Collection: bm25_statement rank 3; character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1779; passage [1379, 1766).

> Input data: an array of integers nums and an integer k. For each unbroken subarray of length k,
> determine the smallest length of a continuous segment that must be sorted so that the entire
> window becomes non‑decreasing; if the window is already sorted, its required length is zero.
> Required result: an array of length n - k + 1 with each element corresponds to the answer for its
> window.

Technical evidence `related-fresh-001-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 158; passage [1454, 1586).

> A better ﬁlter to use in this case is themedian ﬁlter, which selects the median value from each
> pixel’s neighborhood (Figure 3.19a).

Rationale: Processing every length-k window and examining local order gives limited practice with neighborhood traversal and ordering around a moving window.

Limitation: It finds a segment whose sorting fixes a window, not the median of that window; no median-selection algorithm is asserted.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-002::lc1515 — Best Position for a Service Centre

Topic: Euclidean nearest-neighbor feature matching. Label: **stretch_connection**.

Collection: bm25_statement rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 758; passage [904, 1184).

> Given customer coordinates positions, choose any point in the plane as a service-center location.
> Minimize the sum of ordinary Euclidean distances from that point to all listed customers. Return
> the least sum, rather than the selected coordinate. Error within 10^-5 is acceptable.

Technical evidence `related-fresh-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 467; passage [1612, 1804).

> To begin with, we assume that the feature descriptors have been designed so that Eu-
> clidean (vector magnitude) distances in feature space can be directly used for ranking poten-
> tial matches.

Technical evidence `related-fresh-002-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 469; passage [1946, 2034).

> A better strategy in such cases is to simply match thenearest
> neighbor in feature space.

Rationale: The objective explicitly sums Euclidean distances between points, giving practice with the same distance measure used to rank feature matches.

Limitation: It optimizes a freely chosen service-center location and returns a sum; it does not find a nearest stored descriptor or rank feature correspondences.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-002::lc1772 — Sort Features by Popularity

Topic: Euclidean nearest-neighbor feature matching. Label: **unrelated**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 887; passage [111, 868).

> Input data: an array of strings features where features[i] is a single word that identifies the name
> of a feature of the latest product you are working on. Available: made a survey where users have
> reported which features they like. Input data: an array of strings responses, with each responses[i]
> is a string containing space-separated words. The popularity of a feature is the count of
> responses[i] that contain the feature. Goal: sort the features in nonincreasing order by their
> popularity. If two features have the same popularity, order them by their original index in features.
> Notice that one response could contain the same feature multiple times; this feature is only
> counted once in its popularity. Required result: the features in sorted order.

Technical evidence `related-fresh-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 467; passage [1612, 1804).

> To begin with, we assume that the feature descriptors have been designed so that Eu-
> clidean (vector magnitude) distances in feature space can be directly used for ranking poten-
> tial matches.

Technical evidence `related-fresh-002-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 469; passage [1946, 2034).

> A better strategy in such cases is to simply match thenearest
> neighbor in feature space.

Rationale: It ranks named product features by how many survey responses mention them, rather than comparing descriptor vectors by Euclidean distance.

Limitation: Feature and ranking vocabulary alone does not establish geometric nearest-neighbor matching.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-002::lc2383 — Minimum Hours of Training to Win a Competition

Topic: Euclidean nearest-neighbor feature matching. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1192; passage [878, 1833).

> You are entering a competition, and are given two positive integers initialEnergy and
> initialExperience denoting your initial energy and initial experience respectively. Input data: two
> indexed from zero integer arrays energy and experience, both of length n. You will face n
> opponents in order. The energy and experience of the i^th opponent is denoted by energy[i] and
> experience[i] respectively. When you face an opponent, you need to have both strictly greater
> experience and energy to defeat them and move to the next opponent if available. Defeating the
> i^th opponent increases your experience by experience[i], but decreases your energy by
> energy[i]. Before starting the competition, you can train for some number of hours. After each hour
> of training, you can either choose to increase your initial experience by one, or increase your initial
> energy by one. Required result: the smallest count of training hours required to defeat all n
> opponents.

Technical evidence `related-fresh-002-t1`: `Computer Vision: Algorithms and Applications.pdf`, physical page 467; passage [1612, 1804).

> To begin with, we assume that the feature descriptors have been designed so that Eu-
> clidean (vector magnitude) distances in feature space can be directly used for ranking poten-
> tial matches.

Technical evidence `related-fresh-002-t2`: `Computer Vision: Algorithms and Applications.pdf`, physical page 469; passage [1946, 2034).

> A better strategy in such cases is to simply match thenearest
> neighbor in feature space.

Rationale: The task minimizes training hours needed to exceed opponents' energy and experience, rather than comparing distances between feature vectors.

Limitation: No spatial distance, nearest-point selection, or descriptor matching is required.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-003::lc1455 — Check If a Word Occurs As a Prefix of Any Word in a Sentence

Topic: Uniform-disk subproblem in Box-Muller sampling. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 728; passage [916, 1375).

> For a sentence that contains some words separated by a single space, and a searchWord, check if
> searchWord is a prefix of any word in sentence. Required result: the index of the word in sentence
> (indexed from one) where searchWord is a prefix of this word. If searchWord is a prefix of more
> than one word, compute the index of the first word (smallest index). If there is no such word
> produce -1. A prefix of a string s is any leading unbroken substring of s.

Technical evidence `related-fresh-003-t1`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [409, 683).

> In this section, we describe a method to sample from a Gaussian. The idea is we sample uniformly
> from a unit radius circle, and then use the change of variables formula to derive samples from a
> spherical 2d Gaussian. This can be thought of as two samples from a 1d Gaussian.

Technical evidence `related-fresh-003-t2`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [789, 859).

> The result will be points uniformly distributed inside the unit circle

Rationale: The task finds a word prefix in a sentence, whereas the source describes random sampling inside a circle.

Limitation: There is no geometric interior test or distribution-sampling operation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-003::lc1828 — Queries on Number of Points Inside a Circle

Topic: Uniform-disk subproblem in Box-Muller sampling. Label: **related_practice**.

Collection: bm25_statement rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 915; passage [127, 630).

> Input data: an array points where points[i] = [x_i, y_i] is the coordinates of the i^th point on a 2D
> plane. Multiple points can have the same coordinates. Input data: an array queries where
> queries[j] = [x_j, y_j, r_j] describes a circle centered at (x_j, y_j) with a radius of r_j. For each query
> queries[j], compute the count of points inside the j^th circle. Points on the border of the circle are
> considered inside. Required result: an array answer, where answer[j] is the answer to the j^th
> query.

Technical evidence `related-fresh-003-t1`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [409, 683).

> In this section, we describe a method to sample from a Gaussian. The idea is we sample uniformly
> from a unit radius circle, and then use the change of variables formula to derive samples from a
> spherical 2d Gaussian. This can be thought of as two samples from a 1d Gaussian.

Technical evidence `related-fresh-003-t2`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [789, 859).

> The result will be points uniformly distributed inside the unit circle

Rationale: Testing which points lie inside a specified circle practices the geometric interior condition that defines the source's uniform-disk sampling domain.

Limitation: It counts fixed supplied points and includes the boundary; it does not generate random points or establish a uniform continuous distribution.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-003::lc2249 — Count Lattice Points Inside a Circle

Topic: Uniform-disk subproblem in Box-Muller sampling. Label: **stretch_connection**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1125; passage [524, 909).

> For a two-dimensional array of integers circles where circles[i] = [x_i, y_i, r_i] identifies the center
> (x_i, y_i) and radius r_i of the i^th circle drawn on a grid, compute the count of lattice points that
> are present inside one or more circle. A lattice point is a point with integer coordinates. Points that
> lie on the circumference of a circle are also considered to be inside it.

Technical evidence `related-fresh-003-t1`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [409, 683).

> In this section, we describe a method to sample from a Gaussian. The idea is we sample uniformly
> from a unit radius circle, and then use the change of variables formula to derive samples from a
> spherical 2d Gaussian. This can be thought of as two samples from a 1d Gaussian.

Technical evidence `related-fresh-003-t2`: `Probabilistic Machine Learning.pdf`, physical page 521; passage [789, 859).

> The result will be points uniformly distributed inside the unit circle

Rationale: Identifying integer-coordinate points inside circles gives limited practice with circle-interior membership, a geometric component related to selecting points within the sampling disk.

Limitation: It counts discrete lattice points in a union of circles rather than sampling continuously and uniformly from one unit disk.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-004::lc444 — Sequence Reconstruction

Topic: Merging sorted storage segments. Label: **unrelated**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 222; passage [588, 857).

> Given nums, a permutation of 1 through n, and sequences, determine whether nums is the unique
> shortest sequence containing every sequence as a subsequence. All precedence relationships
> must be satisfied, and no alternative shortest ordering may exist. Return a boolean.

Technical evidence `related-fresh-004-t1`: `Designing Data-Intensive Applications.pdf`, physical page 98; passage [857, 1276).

> Merging segments is simple and efficient, even if the files are bigger than the
> available memory. The approach is like the one used in the mergesort algorithm
> and is illustrated in Figure 3-4: you start reading the input files side by side, look
> at the first key in each file, copy the lowest key (according to the sort order) to
> the output file, and repeat. This produces a new merged segment file, also sorted
> by key.

Rationale: The statement checks uniqueness of a sequence under precedence constraints, rather than repeatedly copying the smallest available key from sorted inputs.

Limitation: Combining sequence constraints does not establish sorted-value merge operations.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-004::lc1356 — Sort Integers by The Number of 1 Bits

Topic: Merging sorted storage segments. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 678; passage [940, 1229).

> Input data: an array of integers arr. Sort the integers in the array in ascending order by the count
> of 1's in their binary representation and in case of two or more integers have the same number of
> 1's you have to sort them in ascending order. Required result: the array after sorting it.

Technical evidence `related-fresh-004-t1`: `Designing Data-Intensive Applications.pdf`, physical page 98; passage [857, 1276).

> Merging segments is simple and efficient, even if the files are bigger than the
> available memory. The approach is like the one used in the mergesort algorithm
> and is illustrated in Figure 3-4: you start reading the input files side by side, look
> at the first key in each file, copy the lowest key (according to the sort order) to
> the output file, and repeat. This produces a new merged segment file, also sorted
> by key.

Rationale: The task sorts an unsorted array using bit counts and numeric tie-breaking; the technical passage merges already sorted segments by their next keys.

Limitation: An implementation using merge sort is possible but unstated and is not grounds for labeling the tasks related.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-004::lc1940 — Longest Common Subsequence Between Sorted Arrays

Topic: Merging sorted storage segments. Label: **related_practice**.

Collection: character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 971; passage [132, 490).

> For an array of integer arrays arrays with each arrays[i] is sorted in strictly increasing order,
> compute an array of integers representing the longest common subsequence among all the arrays.
> A subsequence is a sequence that can be derived from another sequence by deleting some
> elements (possibly none) without changing the order of the remaining elements.

Technical evidence `related-fresh-004-t1`: `Designing Data-Intensive Applications.pdf`, physical page 98; passage [857, 1276).

> Merging segments is simple and efficient, even if the files are bigger than the
> available memory. The approach is like the one used in the mergesort algorithm
> and is illustrated in Figure 3-4: you start reading the input files side by side, look
> at the first key in each file, copy the lowest key (according to the sort order) to
> the output file, and repeat. This produces a new merged segment file, also sorted
> by key.

Rationale: Coordinating several strictly sorted input sequences to obtain a common ordered subsequence gives practice with comparing values across sorted inputs.

Limitation: The objective keeps only shared values, rather than merging every input key into one sorted segment. No particular pointer-based solution is claimed.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-004::lc1966 — Binary Searchable Numbers in an Unsorted Array

Topic: Merging sorted storage segments. Label: **unrelated**.

Collection: character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 984; passage [130, 1166).

> Consider a function that implements an algorithm similar to Binary Search. The function has two
> input parameters: sequence is a sequence of integers, and target is an integer value. The purpose
> of the function is to find if the target exists in the sequence. The pseudocode of the function is as
> follows: func(sequence, target) while sequence is not empty randomly choose an element from
> sequence as the pivot if pivot = target, produce true else if pivot < target, remove pivot and all
> elements to its left from the sequence else, remove pivot and all elements to its right from the
> sequence end while produce false When the sequence is sorted, the function works correctly for all
> values. When the sequence is not sorted, the function does not work for all values, but may still
> work for some values. With an array of integers nums, representing the sequence, that contains
> unique numbers and may or may not be sorted, produce the count of values that are guaranteed
> to be found using the function, for every possible pivot selection.

Technical evidence `related-fresh-004-t1`: `Designing Data-Intensive Applications.pdf`, physical page 98; passage [857, 1276).

> Merging segments is simple and efficient, even if the files are bigger than the
> available memory. The approach is like the one used in the mergesort algorithm
> and is illustrated in Figure 3-4: you start reading the input files side by side, look
> at the first key in each file, copy the lowest key (according to the sort order) to
> the output file, and repeat. This produces a new merged segment file, also sorted
> by key.

Rationale: The task studies which values an interval-discarding search finds in an unsorted array; the source combines sorted streams into sorted output.

Limitation: The common sorted-sequence context does not require multi-input merging or next-key selection.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-005::lc597 — Friend Requests I: Overall Acceptance Rate

Topic: Timestamp-based sliding-window rate limiting. Label: **unrelated**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 299; passage [267, 448).

> Compute the
> number of distinct accepted ordered person pairs divided by distinct requested ordered pairs.
> Return accept_rate rounded to two decimals, or zero when no requests exist.

Technical evidence `related-fresh-005-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1306, 1488).

> We can maintain a sliding window if we can keep track of each request per user. We 
> can store the timestamp of each request in a Redis Sorted Set in our ‘value’ field of 
> hash-table.

Technical evidence `related-fresh-005-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1658, 1753).

> 1. Remove all the timestamps from the Sorted Set that are older than 
> “CurrentTime - 1 minute”.

Technical evidence `related-fresh-005-t3`: `Grokking-the-system-design-interview-free.pdf`, physical page 108; passage [7, 212).

> 2. Count the total number of elements in the sorted set. Reject the request if this 
> count is greater than our throttling limit of “3”. 
> 3. Insert the current time in the sorted set and accept the request.

Rationale: The task divides distinct accepted person pairs by distinct requested pairs; the source counts each user's recent timestamps and enforces a rolling-window limit.

Limitation: It computes an aggregate acceptance ratio, not a timestamp-window admission decision. Only the prose computation is used, not schema-table interpretation.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-005::lc1403 — Minimum Subsequence in Non-Increasing Order

Topic: Timestamp-based sliding-window rate limiting. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 702; passage [770, 1350).

> For the array nums, obtain a subsequence of the array whose sum of elements is strictly greater
> than the total of the non included elements in such subsequence. If there are multiple solutions,
> compute the subsequence with smallest size and if there still exist multiple solutions, produce the
> subsequence with the largest total sum of all its elements. A subsequence of an array can result by
> erasing some (possibly zero) elements from the array. Note that the solution with the given
> constraints is guaranteed to be unique. Also produce the answer sorted in nonincreasing order.

Technical evidence `related-fresh-005-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1306, 1488).

> We can maintain a sliding window if we can keep track of each request per user. We 
> can store the timestamp of each request in a Redis Sorted Set in our ‘value’ field of 
> hash-table.

Technical evidence `related-fresh-005-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1658, 1753).

> 1. Remove all the timestamps from the Sorted Set that are older than 
> “CurrentTime - 1 minute”.

Technical evidence `related-fresh-005-t3`: `Grokking-the-system-design-interview-free.pdf`, physical page 108; passage [7, 212).

> 2. Count the total number of elements in the sorted set. Reject the request if this 
> count is greater than our throttling limit of “3”. 
> 3. Insert the current time in the sorted set and accept the request.

Rationale: It selects an array subsequence whose sum exceeds its complement, rather than admitting requests according to recent timestamp counts.

Limitation: There is no time window, per-user event state, or rate limit.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-005::lc3851 — Maximum Requests Without Violating the Limit

Topic: Timestamp-based sliding-window rate limiting. Label: **direct_match**.

Collection: bm25_statement rank 1; character_4gram_tfidf rank 2.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 1927; passage [774, 1269).

> Input data: a two-dimensional array of integers requests, where requests[i] = [user_i, time_i]
> specifies that user_i made a request at time_i. Input data: two integers k and window. A user
> violates the limit if there exists an integer t such that the user makes strictly more than k requests
> in the inclusive interval [t, t + window]. Permitted: drop any number of requests. Required result:
> an integer denoting the largest count of requests that can remain such that no user violates the
> limit.

Technical evidence `related-fresh-005-t1`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1306, 1488).

> We can maintain a sliding window if we can keep track of each request per user. We 
> can store the timestamp of each request in a Redis Sorted Set in our ‘value’ field of 
> hash-table.

Technical evidence `related-fresh-005-t2`: `Grokking-the-system-design-interview-free.pdf`, physical page 107; passage [1658, 1753).

> 1. Remove all the timestamps from the Sorted Set that are older than 
> “CurrentTime - 1 minute”.

Technical evidence `related-fresh-005-t3`: `Grokking-the-system-design-interview-free.pdf`, physical page 108; passage [7, 212).

> 2. Count the total number of elements in the sorted set. Reject the request if this 
> count is greater than our throttling limit of “3”. 
> 3. Insert the current time in the sorted set and accept the request.

Rationale: It explicitly groups timestamped requests by user and enforces a maximum count within a sliding time interval, matching the source's per-user rolling-window limit.

Limitation: It maximizes the requests retained by dropping some offline; the technical passage describes an online remove/count/accept-or-reject procedure and a particular one-minute limit.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-006::lc789 — Escape The Ghosts

Topic: Run-length compression of repeated column values. Label: **unrelated**.

Collection: seeded_random.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 395; passage [98, 307).

> You start at the origin; ghosts start at supplied coordinates. Everyone can move one cardinal step
> or stay each turn. Return whether you can reach target before any ghost can intercept, including
> arrival ties.

Technical evidence `related-fresh-006-t1`: `Designing Data-Intensive Applications.pdf`, physical page 122; passage [1189, 1603).

> Another advantage of sorted order is that it can help with compression of columns. If
> the primary sort column does not have many distinct values, then after sorting, it will
> have long sequences where the same value is repeated many times in a row. A simple
> run-length encoding, like we used for the bitmaps in Figure 3-11 , could compress
> that column down to a few kilobytes—even if the table has billions of rows.

Rationale: The statement compares arrival and interception on a grid; the technical mechanism compresses repeated consecutive values into runs.

Limitation: There is no repeated-run representation, count/value encoding, or decompression.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-006::lc1313 — Decompress Run-Length Encoded List

Topic: Run-length compression of repeated column values. Label: **related_practice**.

Collection: character_4gram_tfidf rank 3.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 657; passage [116, 516).

> We are given a list nums of integers representing a list compressed with run-length encoding.
> Consider each adjacent pair of elements [freq, val] = [nums[2*i], nums[2*i+1]] (with i >= 0). For
> each such pair, there are freq elements with value val concatenated in a sublist. Concatenate all
> the sublists in left-to-right order to generate the decompressed list. Required result: the
> decompressed list.

Technical evidence `related-fresh-006-t1`: `Designing Data-Intensive Applications.pdf`, physical page 122; passage [1189, 1603).

> Another advantage of sorted order is that it can help with compression of columns. If
> the primary sort column does not have many distinct values, then after sorting, it will
> have long sequences where the same value is repeated many times in a row. A simple
> run-length encoding, like we used for the bitmaps in Figure 3-11 , could compress
> that column down to a few kilobytes—even if the table has billions of rows.

Rationale: Interpreting consecutive frequency/value pairs to reconstruct repeated values practices the same run-count representation used in run-length encoding.

Limitation: It decompresses an existing encoded list rather than compressing a sorted database column.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.

## related-fresh-006::lc1531 — String Compression II

Topic: Run-length compression of repeated column values. Label: **related_practice**.

Collection: bm25_statement rank 2; character_4gram_tfidf rank 1.

Problem: `LeetCode_4000_Problem_Reference.pdf`, physical page 766; passage [557, 1130).

> Run-length encoding is a string compression method that works by replacing successive identical
> characters (repeated 2 or more times) with the concatenation of the character and the number
> marking the count of the characters (length of the run). Notice that in this problem, we are not
> adding '1' after single characters. With a string s and an integer k. The task is to delete at most k
> characters from s such that the run-length encoded version of s has smallest length. Find the
> smallest length of the run-length encoded version of s after deleting at most k characters.

Technical evidence `related-fresh-006-t1`: `Designing Data-Intensive Applications.pdf`, physical page 122; passage [1189, 1603).

> Another advantage of sorted order is that it can help with compression of columns. If
> the primary sort column does not have many distinct values, then after sorting, it will
> have long sequences where the same value is repeated many times in a row. A simple
> run-length encoding, like we used for the bitmaps in Figure 3-11 , could compress
> that column down to a few kilobytes—even if the table has billions of rows.

Rationale: It explicitly uses counts of successive identical characters to define a run-length-compressed representation, sharing the source's repeated-value compression mechanism.

Limitation: It additionally chooses character deletions to minimize encoded length; the source discusses already sorted column values and does not require such edit optimization.

Review: automated `codex_source_audit`; human reviewed: false. Model: Codex; exact serving identifier unavailable.
