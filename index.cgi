#!/usr/bin/perl -Tw
#
# unbloat - a minimalist wiki engine
#
# Copyright © 2007-2008 Matti Pöllä <mpo@iki.fi>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

use strict;
use warnings;
use CGI ':standard';
use File::Temp qw/ :POSIX /;
use File::Copy;
use utf8;
#use version; our $VERSION = qv('1.0.0');

# Print error messages properly.
sub err { print '<p class="error">Error: ' . shift() . '</p>' or die "$!"; return; }

# Clear PATH variable for security.
$ENV{"PATH"} = q{};

# Untaint page name
my $page = param('page');
my $rev = param('rev');
$page =~ s/\s+/_/gixm;            # space --> underscore
$page = lc $page;                 # lowercase
$page =~ /([a-z0-9_]+)/xm;        # allow only alphanumeric and underscore
my $un_page = $1 || 'start';      # 'start' is the default page
$un_page =~ s/[^a-z0-9_]//gixm;
$un_page =~ s/_*$//gixm;

my $pagef;
if (! $rev) { $pagef= './pages/' . $un_page; }
else { $pagef= './pages/REV/' . $un_page . "_" . $rev; }

# Page revision code containing date, time and three digits of salt
# Example: 2008-11-27_21:38:39_873
$rev =~ /([0-9_\:\-]+)/gxm; # untaint version string

my $q = new CGI;
print $q->header({-charset =>'utf-8'}) or err();
print $q->start_html({-encoding =>'utf-8', style =>'./style.css', -title =>$un_page}) or err();

# For each time the script is used to generate a wiki page one of the
# following actions is selected
#
#   index    - display a list of all pages that have been written 
#   view     - display a specific page (the default action)
#   edit     - open a page for editing
#   save     - update a page with new contents given as a parameter
#   versions - show a list of page revisions
my $action = 'view';

# The preferred action can be either given explicitly as a parameter
# of the HTTP request or determined inside this script. First, we handle
# the case of an explicitely given action and untaint the input parameter.
my $eaction = param('action');
$eaction =~ s/^([a-z]+)$/$1/gxm;

# Display page revision history
if ($eaction eq 'versions') {
  print "<h1>$un_page</h1>\n<h3>revision history</h3>\n<div class=\"revisions\">\n<pre>" or err();
  print "<a class=\"indexlist\" href=\"index.cgi?page=$un_page\">current</a>\n" or err();
  foreach my $p (reverse glob "./pages/REV/$un_page" . "_*") {
    $p =~ s/\.\/pages\/REV\/$un_page\_//ixm;
    print "<a class=\"indexlist\" href=\"index.cgi?page=$un_page&rev=$p\">$p</a>\n" or err();
  }
  print "\n</pre>\n</div>\n" or err();
  print '<p class="sig"><a class="sig" href="http://github.com/mpolla/unbloat">Unbloat</a></p>' or err();
  print $q->end_html or err();
  exit 0;
}

# Display a list of available pages
if ($eaction eq 'index') {
  print "<h1>page index</h1>\n<div class=\"page\">\n<pre>" or err();
  foreach my $p (glob "./pages/*") {
    $p =~ s/\.\/pages\///ixm;
    print "<a class=\"indexlist\" href=\"index.cgi?page=$p\">$p</a>\n" unless ($p eq 'REV');
  }
  print "</pre></div>\n" . '<p class="sig"><a class="sig" href="http://github.com/mpolla/unbloat">Unbloat</a></p>' or err();
  print $q->end_html or err();
  exit 0;
}

# If the page exists, view it - if not, start editing it
if (! -e $pagef) { $action = 'edit' unless $rev; }

# ..unless an the action is explicitly given
if ($eaction) { $action = $eaction unless $rev; }

# Print page name
print "<h1>$un_page</h1>\n"; print "<h3>[revision $rev]</h3>\n" if $rev;

# When saving, put the contents of the textarea in a temporary file
# and then overwrite the current page file.
if ($action eq 'save') {
  my $te_content = param('content');
  $te_content =~ s/\[\[\s*(.*?)\s*\]\]/\[\[$1\]\]/gxm;
  $te_content =~ s/</\&lt\;/gxm; # Remove angle braces of injected HTML
  $te_content =~ s/>/\&gt\;/gxm;
  my $tmpfile = tmpnam();
  open my $TMPFILE, '>:utf8', $tmpfile or err "Could not write to temporary file $tmpfile: $!";
  print {$TMPFILE} $te_content or err();
  close $TMPFILE or err "Could not close file: $!";
  (my $sec,my $min,my $hour,my $mday,my $mon,my $year,my $wday,my $yday,my $isdst) = localtime(time);
  my $revfile = './pages/REV/' . $un_page . "_" . sprintf "%4d-%02d-%02d_%02d:%02d:%02d_%i", $year+1900,$mon+1,$mday,$hour,$min,$sec,rand()*1000;
  copy $tmpfile, $revfile or err "Could not close file $pagef: $!";
  move $tmpfile, $pagef or err "Could not close file $pagef: $!";
  # Delete file if empty but not the start page.
  unlink $pagef or err "Deleting file failed: $!" if ((! -s $pagef) && $page ne 'start');
  # Then proceed by viewing the page
  $action = 'view';
}

# Read page contents from text file
my @lines;
if (-e $pagef) {
  open my $PAGE, '<:utf8', $pagef or err "Could not open file $pagef: $!";
  @lines = <$PAGE>;
  close $PAGE or err "Could not close file $pagef: $!";;
}

# Merely display the contents of a page.
if ($action eq 'view') {
  if (-e $pagef) {
    print '<div class="page"><pre>' or err();
    foreach (@lines) {
      s/\[\[(https?\:\/\/.*?)\|(.*?)\]\]/<a href="$1">$2<\/a>/gixm;
      s/\[\[(https?\:\/\/.*?)\]\]/<a href="$1">$1<\/a>/gixm;
      s/\[\[(.*?)\|(.*?)\]\]/<a href="index.cgi?page=$1">$2<\/a>/gixm;
      s/\[\[(.*?)\]\]/<a href="index.cgi?page=$1">$1<\/a>/gixm;
      s/\\([\[\]])/$1/gixm;
      print or err();
    }
    print '</pre></div>' or err();
  }
  # Action buttons below the page
  print $q->startform({-method=>'POST', -action=>'index.cgi'}) . $q->hidden({-name=>'page', -default=>$page}) or err(); 
  print $q->submit({-name=>'action', -value=>'edit'}) unless $rev;
  print $q->submit({-name=>'action', -value=>'index'}) . $q->submit({-name=>'action', -value=>'versions'}) or err();
  print $q->endform or err();
}

# When editing a page, insert the contents in a textarea.
elsif ($action eq 'edit') {
  print $q->startform({-method=>'POST', -action=>'index.cgi'}) . $q->hidden({-name=>'page', -default=>$page}) or err();
  print $q->textarea({-name=>'content', -default=>join(q{},@lines), -rows=>20, -columns=>100}) or err();
  print $q->br . $q->submit({-name=>'action', -value=>'save'}) . $q->endform or err();
}
print '<p class="sig"><a class="sig" href="http://github.com/mpolla/unbloat">Unbloat</a></p>' . $q->end_html or err();

