## Extrasolar

**The code in this repository was used by [Extrasolar](http://www.extrasolar.com), a game where you explored a mysterious planet from the comfort of a web browser.**

From the [postmortem website](http://www.extrasolar.com):
"From February 17, 2014 until December 1, 2018, this site hosted an unusual game called Extrasolar that was unlike anything before it. Inspired by Alternate Reality Games (ARGs), it used videos, cloud-rendered imagery, email, terminal systems, phone calls, PDF files, and a collection of website to tell a story that was half about exploring an alien planet and half about playing a pivotal role in a drama that's unfolding back on Earth.

Despite a cult following, the game was never self-sustaining. ... One of the challenges with this type of unusal game is that once it's gone, it's hard for other developers to study it. It's also a shame when a great story disappears from the world."

[Full game credits](https://www.exoresearch.com/credits/)

For more information about the game, visit [What Is Extrasolar?](https://www.whatisextrasolar.com)

### Additional Details

- This archive is a snapshot (circa 2014) of a portion of the game code. It includes the Python backend, which implemented a portion of the story logic, and as well as the Javascript frontend for the web client.
- It does not include the graphics renderer for the planet imagery or the native client wrapper.
- The game was hosted on AWS using Elastic Beanstalk, RDS, S3, SES, and other resources.
- This archive is presented as a reference and historical record and is not expected to be runnable.

The code herein had contributions from (in alphabetical order):

- Rob Jagnow
- Jonathan Le Plastrier
- Keith Turkowski
- Ryan Williams

### Directory Contents

- backend      -- Various core backend services, including the payment system (shop)
- callbacks    -- Game specific logic, called by generic game engine code, dispatched by 'events'
- cron         -- Code meant to be run periodically in production
- data         -- Code and .json/.yaml files for game data. Includes data validation.
- debug        -- Code meant to only be run in development, mainly Route/Story tool
- lib          -- Shared library code
- lib/db       -- Database abstraction, includes migrations
- models       -- Server side data model classes
- public/js    -- Client side Javascript code in ce4 namespace
- resources    -- The web application nodes (url handlers)
- templates    -- Mako templates used by the resources, messages, and emails
- tests        -- Unit, integration and Javascript tests. Doctests also used throughout.
- tools        -- Tools meant to be run in development only

### Notable Python Dependencies

- Beaker          -- Used for web session management
- Mako            -- Used for server side templating
- Paste           -- Used for WSGI web container management
- py-bcrypt       -- Used to encrypt user password
- py-moneyed      -- Used for formatting and converting money and currencies.
- restish         -- Used for REST resource handling
- Spawning        -- Development web server
- stripe          -- Used for processing transactions
- validictory     -- Used to validate data files and gamestate JSON
- WebTest         -- Unit testing harness for WSGI applications
- yoyo-migrations -- Used for database migrations.


### License and Copyright

Extrasolar® is a registered trademark of Lazy 8 Studios.

The story, characters, text, images, and related assets are:

*Copyright (c) 2010-2014 Lazy 8 Studios, LLC. All rights reserved.*

The Python and Javascript source code are made available under the following MIT License:

Copyright (c) 2010-2014 Lazy 8 Studios, LLC.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

