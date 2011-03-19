import os
import sys
import re
import string
from urllib import urlretrieve
from urllib2 import urlopen
from datetime import date

import mutagen.mp3
import mutagen.easyid3

class MP3File(object):
  def __init__(self, filename):
    self.filename = filename
  
  def write_tags(self, **tags):
    m = mutagen.mp3.MP3(self.filename, ID3=mutagen.easyid3.EasyID3)
    if not m.tags:
      m.add_tags(ID3=mutagen.easyid3.EasyID3)
    for tag, value in tags.iteritems():
      m[tag] = value
    m.save()

class StreamingMP3(object):
  def __init__(self, url):
    self.url = url
  
  @property
  def filename(self):
    return re.findall("[^/]*\\.mp3", self.url)[-1]
  
  def save(self, target=None, reporthook=None):
    target = self.filename if target is None else target
    try:
      urlretrieve(self.url, target + ".temp", reporthook=reporthook)
      os.rename(target + ".temp", target)
    except IOError:
      print 'failed'
    return MP3File(target)

class MP3Page(object):
  def __init__(self, url):
    self.url = url
    self._source = urlopen(self.url).read()
  
  @property
  def mp3s(self):
    mp3_urls = re.findall('http[^";,]*\\.mp3[^"]*', self._source)
    return [StreamingMP3(url) for url in mp3_urls]
  
  @property
  def domain(self):
    return re.findall("[^/\.]*(?=\..{3}/)", self.url)[0]

class MP3Scraper(object):
  def __init__(self, url, label, directory='.', delete_old_files=True,
               apply_id3_tags=True, max_files=30):
    self._page = MP3Page(url)
    self._label = label
    self._directory = directory
    self._delete_old_files = delete_old_files
    self._apply_id3_tags = apply_id3_tags
    self._max_files = max_files
    self._original_dir = os.getcwd()
  
  def run(self):
    print self._label
    
    # Switch into target directory, creating it if necessary.
    dir = os.path.join(self._directory, self._slugify(self._label))
    if not os.path.isdir(dir):
      os.makedirs(dir)
    os.chdir(dir)

    # Get mp3s.
    print "scraping %s" % self._page.url
    mp3s = self._page.mp3s
    track = 0
    new_files = False
    for mp3 in mp3s[:self._max_files]:
      track += 1
      if os.path.exists(mp3.filename):
        # Don't replace pre-existing files.
        print 'skipping %s' % mp3.filename
        mp3_file = MP3File(mp3.filename)
      else:
        print 'downloading %s...     ' % mp3.filename,
        mp3_file = mp3.save(reporthook=self._report_progress)
        print
        new_files = True
      if self._apply_id3_tags and new_files:
        mp3_file.write_tags(artist='Podcast', album=self._label,
                            title=mp3.filename[:-4], tracknumber=str(track),
                            date=str(date.today().year), genre='Podcast')
    if self._delete_old_files and len(mp3s) > 0:
      downloaded_files = set([mp3.filename for mp3 in mp3s])
      existing_files = set(os.listdir(os.curdir))
      for filename in existing_files.difference(downloaded_files):
        print 'removing %s' % filename
        os.remove(filename)
          
    # Change back to the initial directory.
    os.chdir(self._original_dir)

  def _report_progress(self, blocks_transferred, block_size, total_size):
    progress_pct = 100 * blocks_transferred * block_size / total_size
    sys.stdout.write("\b\b\b\b%3d%%" % min(100, progress_pct))
  
  def _slugify(self, value):
    valid_chars = "-_() " + string.ascii_letters + string.digits
    return filter(lambda x: x in valid_chars, value)

if __name__ == '__main__':
  from ConfigParser import SafeConfigParser

  config = SafeConfigParser()
  config.read('npr-buddy.ini')
  for label in sorted(config.sections()):
    url = config.get(label, 'url')
    directory = config.get(label, 'directory')
    apply_id3_tags = config.get(label, 'apply_id3_tags')
    delete_old_files = config.getboolean(label, 'delete_old_files')
    max_files = config.getint(label, 'max_files')
    MP3Scraper(url, label, directory=directory,
               delete_old_files=delete_old_files,
               apply_id3_tags=apply_id3_tags, max_files=max_files).run()
    print