from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from mkt.forms import CreateForm, CommentForm
from mkt.models import Ad, Comment, Fav
from mkt.owner import OwnerListView, OwnerDetailView, OwnerCreateView, OwnerUpdateView, OwnerDeleteView


class AdListView(OwnerListView):
    model = Ad
    template_name = "mkt/ad_list.html"

    def get(self, request) :
        str_value = request.GET.get("search", False)

        # ad_list = Ad.objects.all()
        favorites = list()
        if request.user.is_authenticated:
            rows = request.user.favorite_ads.values('id')
            print(rows)
            # favorites = [2, 4, ...] using list comprehension
            favorites = [ row['id'] for row in rows ]
        print(favorites)

        if str_value:
            query = Q(title__icontains=str_value)
            query.add(Q(text__icontains=str_value), Q.OR)
            ad_list = Ad.objects.filter(query).select_related().distinct().order_by('-updated_at')[:10]
        else:
            ad_list = Ad.objects.all().order_by('-updated_at')[:10]

        for obj in ad_list:
            obj.natural_updated = naturaltime(obj.updated_at)

        ctx = {'ad_list' : ad_list, 'favorites': favorites}
        return render(request, self.template_name, ctx)



class AdDetailView(OwnerDetailView):
    model = Ad
    template_name = "mkt/ad_detail.html"
    def get(self, request, pk):
        ad = get_object_or_404(Ad, id=pk)
        comments = Comment.objects.filter(ad=ad).order_by('-updated_at')
        comment_form = CommentForm()
        context = {'ad': ad, 'comments': comments, 'comment_form': comment_form}
        return render(request, self.template_name, context)


class AdCreateView(OwnerCreateView):
    template_name = 'mkt/ad_form.html'
    success_url = reverse_lazy('mkt:all')

    def get(self, request, pk=None):
        form = CreateForm()
        ctx = {'form': form}
        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        form = CreateForm(request.POST, request.FILES or None)

        if not form.is_valid():
            ctx = {'form': form}
            return render(request, self.template_name, ctx)

        # Add owner to the model before saving
        pic = form.save(commit=False)
        pic.owner = self.request.user
        pic.save()
        form.save_m2m()
        return redirect(self.success_url)


class AdUpdateView(OwnerUpdateView):
    template_name = 'mkt/ad_form.html'
    success_url = reverse_lazy('ads:all')

    def get(self, request, pk):
        pic = get_object_or_404(Ad, id=pk, owner=self.request.user)
        form = CreateForm(instance=pic)
        ctx = {'form': form}
        return render(request, self.template_name, ctx)

    def post(self, request, pk=None):
        pic = get_object_or_404(Ad, id=pk, owner=self.request.user)
        form = CreateForm(request.POST, request.FILES or None, instance=pic)

        if not form.is_valid():
            ctx = {'form': form}
            return render(request, self.template_name, ctx)

        pic = form.save(commit=False)
        pic.save()
        form.save_m2m()

        return redirect(self.success_url)

class AdDeleteView(OwnerDeleteView):
    model = Ad

class CommentCreateView(LoginRequiredMixin, View):
    def post(self, request, pk) :
        ad = get_object_or_404(Ad, id=pk)
        comment = Comment(text=request.POST['comment'], owner=request.user, ad=ad)
        comment.save()
        return redirect(reverse('mkt:ad_detail', args=[pk]))

class CommentDeleteView(OwnerDeleteView):
    model = Comment
    template_name = "mkt/ad_comment_delete.html"

    # https://stackoverflow.com/questions/26290415/deleteview-with-a-dynamic-success-url-dependent-on-id
    def get_success_url(self):
        ad = self.object.ad
        return reverse('mkt:ad_detail', args=[ad.id])

@method_decorator(csrf_exempt, name='dispatch')
class ToggleFavoriteView(LoginRequiredMixin, View):

    def post(self, request, pk) :
        t = get_object_or_404(Ad, id=pk)
        fav = Fav(user=request.user, ad=t)
        try:
            fav.save()
            return HttpResponse("Favorite added 42")
        except IntegrityError:  # Already there, lets delete...
            Fav.objects.get(user=request.user, ad=t).delete()
            return HttpResponse("Favorite deleted 42")

def stream_file(request, pk):
    pic = get_object_or_404(Ad, id=pk)
    response = HttpResponse()
    response['Content-Type'] = pic.content_type
    response['Content-Length'] = len(pic.picture)
    response.write(pic.picture)
    return response
